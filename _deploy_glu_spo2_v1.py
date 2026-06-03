import paramiko, time, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DID}"

def sh(c, cmd, t=600):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    if out.strip():
        print(out[-4000:])
    if err.strip():
        print("[stderr]", err[-2000:])
    return out, err

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)
print("SSH connected")

# 1) fetch latest code
sh(c, f"cd {PROJ} && git fetch origin --depth 1 --no-tags 2>&1 | tail -5", 120)
sh(c, f"cd {PROJ} && git reset --hard origin/master && git log -1 --oneline", 120)

# 2) find gateway container
gw, _ = sh(c, "docker ps --format '{{.Names}}' | grep -i gateway")
GW = gw.strip().splitlines()[0] if gw.strip() else "gateway-nginx"
print("Gateway container:", GW)

# 3) rebuild h5 only (backend only got a test file, no business change)
sh(c, f"cd {PROJ} && BUILD_COMMIT=$(git log -1 --format=%H) && echo BUILD_COMMIT=$BUILD_COMMIT > .env.build && (grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null; mv .env.tmp .env 2>/dev/null; true) && echo BUILD_COMMIT=$BUILD_COMMIT >> .env && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -25", 1800)
sh(c, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -15", 300)

# 4) wait for h5 healthy
for i in range(24):
    out, _ = sh(c, f"docker ps --filter name={DID}-h5 --format '{{{{.Status}}}}'")
    if "healthy" in out or "Up" in out:
        if "unhealthy" not in out and "starting" not in out:
            print("h5 up:", out.strip())
            break
    time.sleep(5)

# 5) reconnect gateway network + reload
sh(c, f"docker network connect {DID}-network {GW} 2>/dev/null || true")
sh(c, f"docker exec {GW} nginx -t 2>&1")
sh(c, f"docker exec {GW} nginx -s reload 2>&1 || true")
time.sleep(2)

c.close()
print("\n=== DEPLOY DONE ===")
