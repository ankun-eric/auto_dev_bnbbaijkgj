import paramiko, sys, os, time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def ssh_exec(cmd, timeout=120):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, PORT, USER, PASS, timeout=30)
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    ec = o.channel.recv_exit_status()
    c.close()
    return out, err, ec

# Step 1: Git pull latest code
print("=== Step 1: Git pull ===")
cmd = f"cd {PROJ_DIR} && timeout 30 git fetch --depth 1 origin master && git reset --hard origin/master && git clean -fd"
out, err, ec = ssh_exec(cmd, timeout=60)
print(f"exit={ec}")
if out: print(out[:500])
if err: print(f"ERR: {err[:500]}")

# Step 2: Check if new files exist
print("\n=== Step 2: Check new files ===")
for f in [
    "backend/app/api/medication_history_v1.py",
    "backend/app/schemas/medication_history.py",
    "h5-web/src/app/(ai-chat)/ai-home/medication-reminder/history/page.tsx",
    "h5-web/src/lib/api/medication.ts"
]:
    out, _, ec = ssh_exec(f"test -f {PROJ_DIR}/{f} && echo 'EXISTS' || echo 'MISSING'")
    print(f"  {f}: {'EXISTS' if 'EXISTS' in out else 'MISSING'}")

# Step 3: Rebuild containers
print("\n=== Step 3: Docker compose build ===")
cmd = f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --pull backend h5-web 2>&1 || docker compose -f docker-compose.prod.yml build backend h5-web 2>&1"
out, err, ec = ssh_exec(cmd, timeout=600)
print(f"Build exit={ec}")
if out: print(out[-500:])
if err: print(f"ERR: {err[-500:]}")

# Step 4: Restart containers
print("\n=== Step 4: Restart containers ===")
cmd = f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend h5-web 2>&1"
out, err, ec = ssh_exec(cmd, timeout=120)
print(f"exit={ec}")
if out: print(out[-500:])
if err: print(f"ERR: {err[-500:]}")

# Step 5: Wait for health
print("\n=== Step 5: Wait for healthy ===")
time.sleep(15)
cmd = "docker ps --format '{{.Names}} {{.Status}}' | findstr 6b099ed3"
out, _, _ = ssh_exec(cmd)
print(out)

# Step 6: Verify new API endpoints
print("\n=== Step 6: Verify new API ===")
cmd = f"docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/api/medication/calendar?year=2026\&month=6 2>&1"
out, _, _ = ssh_exec(cmd)
print(f"  /api/medication/calendar?year=2026&month=6: HTTP {out.strip()}")

cmd = f"docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/api/medication/records?date=2026-06-07 2>&1"
out, _, _ = ssh_exec(cmd)
print(f"  /api/medication/records?date=2026-06-07: HTTP {out.strip()}")

cmd = f"docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/docs 2>&1"
out, _, _ = ssh_exec(cmd)
print(f"  /docs: HTTP {out.strip()}")

print("\n=== DONE ===")
