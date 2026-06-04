"""
Fix: add codeup remote on server, pull latest code, rebuild with healthchecks.
"""
import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BUILD_COMMIT = "b0126a1cf95b8fe71b80f2f0d25c540c3e740a04"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
GATEWAY_CONF_SRC = f"{PROJECT_DIR}/gateway-routes.conf"
GATEWAY_CONF_DST = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"
GATEWAY_CONTAINER = "gateway-nginx"
COUP_URL = "https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(f"cd {PROJECT_DIR} && {cmd}", timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace').strip(), stderr.read().decode('utf-8', errors='replace').strip()

def run_raw(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace').strip(), stderr.read().decode('utf-8', errors='replace').strip()

print("=== Fix 1: Check git remote ===")
out, err = run_raw(f"cd {PROJECT_DIR} && git remote -v")
print(out)

print("\n=== Fix 2: Add codeup remote if missing ===")
if "codeup" not in out:
    out, err = run_raw(f"cd {PROJECT_DIR} && git remote add codeup {COUP_URL}")
    print(f"Added: {out} {err}")
    out, err = run_raw(f"cd {PROJECT_DIR} && git remote set-url codeup {COUP_URL} 2>&1")
    print(f"Set URL: {out} {err}")

print("\n=== Fix 3: Git pull ===")
out, err = run("git pull codeup master 2>&1", timeout=30)
print(f"Pull: {out[:500]}")
if err:
    print(f"Err: {err[:300]}")

print("\n=== Fix 4: Verify docker-compose.prod.yml has healthchecks ===")
out, err = run("grep -c healthcheck docker-compose.prod.yml")
print(f"healthcheck count in compose: {out}")

print("\n=== Fix 5: Rebuild with healthchecks (only if needed) ===")
if out.strip() != "4":
    print("Healthchecks missing, rebuilding...")
    out, err = run("docker compose -f docker-compose.prod.yml down 2>&1", timeout=60)
    print(f"Down: {out[:200]}")
    out, err = run(f"BUILD_COMMIT={BUILD_COMMIT} docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    # Just check last few lines
    lines = out.strip().split('\n')
    for line in lines[-10:]:
        print(f"  Build: {line}")
    out, err = run("docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)
    print(f"Up: {out[:200]}")
    
    print("\n=== Wait for healthy ===")
    for i in range(20):
        time.sleep(10)
        out, err = run("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'", timeout=10)
        print(f"  [{i+1}] {out}")
        if out and all('Up' in l for l in out.split('\n')):
            print("  All up!")
            break
else:
    print("Healthchecks already present, no rebuild needed")

print("\n=== Fix 6: Update gateway config ===")
out, err = run_raw(f"cp {GATEWAY_CONF_SRC} {GATEWAY_CONF_DST} 2>&1")
print(f"cp: {out} {err}")

out, err = run_raw(f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
print(f"nginx -t: {out[:200]}")
out, err = run_raw(f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
print(f"reload: {out[:200]}")

print("\n=== Fix 7: Verify HTTPS ===")
out, err = run_raw(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health 2>&1")
print(f"/api/health: HTTP {out}")
out, err = run_raw(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/ 2>&1")
print(f"/ : HTTP {out}")
out, err = run_raw(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/ 2>&1")
print(f"/admin/: HTTP {out}")

print("\n=== Fix 8: Check admin account via backend container ===")
out, err = run_raw(
    f"docker exec {DEPLOY_ID}-backend python3 -c \""
    "import asyncio; "
    "from app.core.database import async_session; "
    "from app.models.models import User; "
    "from sqlalchemy import select; "
    "async def check(): "
    "  async with async_session() as db: "
    "    r = await db.execute(select(User).where(User.username == 'admin')); "
    "    u = r.scalar_one_or_none(); "
    "    if u: print(f'admin EXISTS, role={u.role}'); "
    "    else: print('admin NOT FOUND'); "
    "asyncio.run(check())"
    "\" 2>&1", timeout=20)
print(f"Admin: {out[:200]}")

print("\n=== Fix 9: Final container status ===")
out, err = run_raw("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
print(out)

print("\n=== DONE ===")
ssh.close()
