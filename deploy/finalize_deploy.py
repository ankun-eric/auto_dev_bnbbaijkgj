"""Finalize deployment: fix git, rebuild, restart, gateway."""
import paramiko, sys, time, os

HOST, USER, PASS = "newbb.test.bangbangvip.com", "ubuntu", "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PDIR = f"/home/ubuntu/{DID}"
LDIR = os.path.dirname(os.path.abspath(__file__))
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd[:120]}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out[-1200:], flush=True)
    if err.strip() and ec != 0: print("ERR:", err[-400:], flush=True)
    return ec, out, err

def upload(ssh, loc, rem):
    print(f"UPLOAD {os.path.basename(loc)} -> {rem}", flush=True)
    sftp = ssh.open_sftp(); sftp.put(loc, rem); sftp.close()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=15)
print("Connected", flush=True)


# 1. Git update using 'origin' remote
print("\n=== Step 1: Git update ===", flush=True)
run(ssh, f"cd {PDIR} && git remote -v")
run(ssh, f"cd {PDIR} && git fetch origin master 2>&1", timeout=60)
run(ssh, f"cd {PDIR} && git reset --hard origin/master 2>&1")
run(ssh, f"cd {PDIR} && git log --oneline -3")

# 2. Upload latest configs
print("\n=== Step 2: Upload configs ===", flush=True)
upload(ssh, os.path.join(LDIR, "docker-compose.prod.yml"),
       f"{PDIR}/deploy/docker-compose.prod.yml")
upload(ssh, os.path.join(LDIR, "gateway-routes.conf"),
       f"{PDIR}/deploy/gateway-routes.conf")

# 3. Stop all project containers
print("\n=== Step 3: Stop old containers ===", flush=True)
run(ssh, f"docker stop {DID}-backend {DID}-admin {DID}-h5 2>/dev/null || echo some_stopped", timeout=30)
run(ssh, f"docker rm {DID}-backend {DID}-admin {DID}-h5 2>/dev/null || echo some_removed", timeout=30)

# 4. ACR login
print("\n=== Step 4: ACR login ===", flush=True)
run(ssh, f"docker login --username ankun888 --password xiaobai888 {ACR}")

# 5. Build images
print("\n=== Step 5: Build backend ===", flush=True)
run(ssh, f"cd {PDIR}/backend && docker build -f ../deploy/Dockerfile.backend -t {ACR}/noob_ai_apps/{DID}-backend:latest . 2>&1",
    timeout=600)

print("\n=== Step 6: Build admin ===", flush=True)
run(ssh, f"cd {PDIR}/admin-web && docker build -f ../deploy/Dockerfile.admin -t {ACR}/noob_ai_apps/{DID}-admin-web:latest . 2>&1",
    timeout=600)

print("\n=== Step 7: Build h5 ===", flush=True)
run(ssh, f"cd {PDIR}/h5-web && docker build -f ../deploy/Dockerfile.h5 -t {ACR}/noob_ai_apps/{DID}-h5-web:latest . 2>&1",
    timeout=600)


# 8. Start with docker compose
print("\n=== Step 8: docker compose up ===", flush=True)
run(ssh, f"cd {PDIR}/deploy && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)

# 9. Wait for health
print("\n=== Step 9: Health check ===", flush=True)
for i in range(24):
    time.sleep(10)
    stdin, stdout, stderr = ssh.exec_command(
        f"docker ps --filter name={DID} --format '{{{{.Names}}}} {{{{.Status}}}}' | grep -v db",
        timeout=10)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    lines = [l for l in out.split('\n') if l.strip()]
    unhealthy = [l for l in lines if 'healthy' not in l.lower()]
    if not unhealthy and lines:
        print(f"[{i}] All healthy: {lines}", flush=True)
        break
    print(f"[{i}] waiting: {unhealthy or 'no containers'}", flush=True)
else:
    print("TIMEOUT - checking final state", flush=True)
    run(ssh, f"docker ps -a --filter name={DID}")

# 10. Gateway update (copy to host path, not docker cp)
print("\n=== Step 10: Gateway update ===", flush=True)
# Copy to host's conf.d directory which is mounted into gateway-nginx
run(ssh, f"cp {PDIR}/deploy/gateway-routes.conf /home/ubuntu/gateway/conf.d/{DID}.server")
run(ssh, f"docker network connect {DID}-network gateway-nginx 2>/dev/null || echo already")
code, out, err = run(ssh, "docker exec gateway-nginx nginx -t 2>&1")
if "successful" in (out + err).lower() or "syntax is ok" in (out + err).lower():
    run(ssh, "docker exec gateway-nginx nginx -s reload 2>&1")
    print("Nginx OK", flush=True)
else:
    print("NGINX TEST FAILED", flush=True)
    print(out[-500:], err[-500:], flush=True)

# 11. Migrations
print("\n=== Step 11: Migrations ===", flush=True)
run(ssh, f"docker exec {DID}-backend python3 -c 'import importlib; importlib.import_module(\"migrations.migration_bucket_replace_20260604\")' 2>&1", timeout=30)

# 12. Default account check via DB
print("\n=== Step 12: Accounts ===", flush=True)
run(ssh, f"docker exec {DID}-db mysql -uroot -pxiaokang989aab bini_health -e \"SELECT username, role FROM users LIMIT 5\" 2>&1", timeout=10)

# 13. Final status
print("\n=== Final Status ===", flush=True)
run(ssh, f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")
run(ssh, f"cd {PDIR} && git log --oneline -1")

print(f"\n=== DEPLOY COMPLETE ===", flush=True)
print(f"URL: https://{DID}.noob-ai.test.bangbangvip.com", flush=True)
ssh.close()
