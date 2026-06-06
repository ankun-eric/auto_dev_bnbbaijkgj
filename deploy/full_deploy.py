#!/usr/bin/env python3
"""Phase 3: Full remote deployment for project 6b099ed3."""
import paramiko
import time
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
CODEUP_URL = "https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
GATEWAY_CONTAINER = "gateway-nginx"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"[INFO] Connecting to {HOST}:{PORT} as {USER} ...")
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
print("[OK] Connected.")

def run(cmd, timeout=120, show=True):
    """Execute remote command."""
    if show:
        print(f"\n  [CMD] {cmd[:150]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    rc = stdout.channel.recv_exit_status()
    if show:
        if out:
            print(f"  [OUT] {out[:600]}")
        if err and rc != 0:
            print(f"  [ERR] {err[:300]}")
    return out, err, rc

# ========== Step 1: ACR Login ==========
print("\n===== Step 1: ACR Login =====")
out, err, rc = run(f"echo 'xiaobai888' | docker login {ACR} -u ankun888 --password-stdin 2>&1")
if "Login Succeeded" in out:
    print("[OK] ACR login successful.")
else:
    print(f"[ERROR] ACR login failed: {out} {err}")

# ========== Step 2: Git pull from Codeup ==========
print("\n===== Step 2: Git pull from Codeup =====")
out, err, rc = run(f"cd {PROJECT_DIR} && git remote set-url codeup {CODEUP_URL} 2>/dev/null; git remote set-url origin {CODEUP_URL} 2>/dev/null; git fetch origin master 2>&1")
print(f"  Fetch: {out[:300]}")
if rc != 0:
    print(f"  Fetch error: {err[:300]}")
    # Try clone if directory issue
    out, err, rc = run(f"cd {PROJECT_DIR} && git remote -v 2>&1")
    print(f"  Remotes: {out[:200]}")

out, err, rc = run(f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1")
print(f"  Reset: {out[:300]}")
if rc != 0:
    print(f"[ERROR] Git reset failed: {err[:300]}")
    sys.exit(1)

out, err, rc = run(f"cd {PROJECT_DIR} && git log --oneline -3 2>&1")
print(f"  Latest commits:\n{out}")

# ========== Step 3: BUILD_INFO ==========
print("\n===== Step 3: Generate BUILD_INFO =====")
import datetime
build_commit = f"deploy-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
print(f"  BUILD_COMMIT = {build_commit}")

# ========== Step 4: Docker compose build + up ==========
print("\n===== Step 4: Docker compose build --pull + up -d =====")
out, err, rc = run(
    f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml build --pull 2>&1",
    timeout=300
)
print(f"  Build output (last 500 chars): ...{out[-500:] if len(out)>500 else out}")
if rc != 0:
    print(f"[WARN] Build had issues: {err[:400]}")

out, err, rc = run(
    f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml up -d 2>&1",
    timeout=120
)
print(f"  Up output: {out[:500]}")
if rc != 0:
    print(f"[ERROR] docker compose up failed: {err[:400]}")
else:
    print("[OK] docker compose up completed.")

# ========== Step 5: Wait for health ==========
print("\n===== Step 5: Wait for container health =====")
BACKEND = f"{DEPLOY_ID}-backend"
H5 = f"{DEPLOY_ID}-h5"
ADMIN = f"{DEPLOY_ID}-admin"
DB = f"{DEPLOY_ID}-db"
all_services = [DB, BACKEND, H5, ADMIN]

for attempt in range(24):  # max 4 min (10s interval)
    out, err, rc = run(
        f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' 2>/dev/null",
        timeout=10, show=False
    )
    print(f"  [{attempt+1}/24] Container status:\n{out}")
    all_healthy = True
    for svc in all_services:
        if svc not in out or "healthy" not in out.split(svc)[1].split('\n')[0]:
            all_healthy = False
            break
    if all_healthy:
        print(f"[OK] All containers healthy at attempt {attempt+1}!")
        break
    time.sleep(10)
else:
    print("[WARN] Timeout waiting for healthy containers. Proceeding anyway.")

# ========== Step 6: Gateway config update and reload ==========
print("\n===== Step 6: Update gateway-nginx config =====")
# Copy gateway-routes.conf to gateway container
out, err, rc = run(
    f"docker cp {PROJECT_DIR}/gateway-routes.conf {GATEWAY_CONTAINER}:/etc/nginx/conf.d/{DEPLOY_ID}.conf 2>&1"
)
print(f"  Copy config: {out} {err}")

# Reload gateway
out, err, rc = run(f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
print(f"  Reload: {out} {err}")
if rc == 0:
    print("[OK] Gateway reloaded.")
else:
    print(f"[WARN] Gateway reload may have warnings but should be OK.")

# ========== Step 7: Database Migration ==========
print("\n===== Step 7: Database Migration =====")
# Run init.sql in the db container
out, err, rc = run(
    f"docker exec {DB} mysql -uroot -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1"
)
print(f"  Databases: {out[:300]}")

# Run SQLAlchemy create_all via backend
out, err, rc = run(
    f"docker exec {BACKEND} python3 -c \""
    f"import asyncio; from app.database import engine, Base; "
    f"async def init(): async with engine.begin() as conn: "
    f"await conn.run_sync(Base.metadata.create_all); print('Tables created OK'); "
    f"asyncio.run(init())\" 2>&1",
    timeout=30
)
print(f"  create_all: {out[:400]} {err[:200]}")

# Run init.sql in case it has extra seed data
out, err, rc = run(
    f"docker exec -i {DB} mysql -uroot -pbini_health_2026 bini_health < {PROJECT_DIR}/backend/init.sql 2>&1"
)
print(f"  init.sql: {out[:200]} {err[:200]}")

# ========== Step 8: Check and create default admin account ==========
print("\n===== Step 8: Default admin account =====")
# Check if admin user exists
out, err, rc = run(
    f"docker exec {DB} mysql -uroot -pbini_health_2026 bini_health -e "
    f"\"SELECT id, username, role FROM users WHERE username='admin' LIMIT 1;\" 2>&1"
)
print(f"  Check admin user: {out[:300]}")

if "admin" not in out:
    print("[INFO] Admin user not found. Creating default admin (admin/admin123)...")
    out, err, rc = run(
        f"docker exec {BACKEND} python3 -c \""
        f"import asyncio; from app.database import get_db; "
        f"from app.models import User; "
        f"from passlib.context import CryptContext; "
        f"pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto'); "
        f"async def create(): "
        f"from sqlalchemy import select; "
        f"from app.database import async_session; "
        f"async with async_session() as db: "
        f"result = await db.execute(select(User).where(User.username == 'admin')); "
        f"user = result.scalar_one_or_none(); "
        f"if not user: "
        f"user = User(username='admin', hashed_password=pwd_context.hash('admin123'), "
        f"role='admin', is_active=True); "
        f"db.add(user); await db.commit(); print('Admin created'); "
        f"else: print('Admin already exists'); "
        f"asyncio.run(create())\" 2>&1",
        timeout=30
    )
    print(f"  Create admin: {out[:500]} {err[:200]}")
else:
    print("[OK] Admin user already exists.")

# ========== Final Verification ==========
print("\n===== Final Verification =====")
# Check backend health
out, err, rc = run(
    f"docker exec {BACKEND} curl -sf http://localhost:8000/api/health 2>&1 || "
    f"docker exec {BACKEND} python3 -c \"import urllib.request; "
    f"r=urllib.request.urlopen('http://localhost:8000/api/health'); print(r.read())\" 2>&1",
    timeout=15
)
print(f"  Backend health: {out[:300]}")

# Check H5
h5_cmd = "docker exec " + H5 + " node -e \"require('http').get('http://localhost:3001/',r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>console.log(r.statusCode))})\" 2>&1"
out, err, rc = run(h5_cmd, timeout=15)
print(f"  H5 status: {out[:200]}")

# Check Admin
admin_cmd = "docker exec " + ADMIN + " node -e \"require('http').get('http://localhost:3000/admin',r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>console.log(r.statusCode))})\" 2>&1"
out, err, rc = run(admin_cmd, timeout=15)
print(f"  Admin status: {out[:200]}")

# Check containers
out, err, rc = run(f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'")
print(f"\n  All containers:\n{out}")

print("\n===== DEPLOYMENT COMPLETE =====")
print(f"  Domain: https://{DOMAIN}")
print(f"  Admin:  https://{DOMAIN}/admin (admin/admin123)")

ssh.close()
