"""
Fixed stage 3 deployment - step by step with proper error handling.
"""
import paramiko
import sys
import time
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DEPLOY_DIR = os.path.dirname(os.path.abspath(__file__))
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
CODEUP_REPO = f"https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
CODEUP_USER = "kun-an"
CODEUP_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"
GIT_URL_WITH_TOKEN = f"https://{CODEUP_USER}:{CODEUP_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd[:120]}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if exit_code != 0:
        print(f"[EXIT={exit_code}]", flush=True)
    if out.strip():
        print(out[:600], flush=True)
    if err.strip() and exit_code != 0:
        print("STDERR:", err[:400], flush=True)
    return exit_code, out, err

def upload(ssh, local, remote):
    print(f"\n>>> UPLOAD {local} -> {remote}", flush=True)
    sftp = ssh.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    print("OK", flush=True)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
print("=== DEPLOY FIX ===", flush=True)


# 1. Fix git remote
print("\n--- Step 1: Fix git remote ---", flush=True)
run(ssh, f"cd {PROJECT_DIR} && git remote -v")
run(ssh, f"cd {PROJECT_DIR} && git remote set-url codeup {GIT_URL_WITH_TOKEN}")
run(ssh, f"cd {PROJECT_DIR} && git remote -v")

# 2. Git fetch + reset
print("\n--- Step 2: Git fetch + reset ---", flush=True)
code, out, err = run(ssh, f"cd {PROJECT_DIR} && git fetch codeup master 2>&1", timeout=60)
if code != 0:
    print("Fetch might have issues, trying force fetch...")
    run(ssh, f"cd {PROJECT_DIR} && git fetch --force codeup master 2>&1", timeout=60)

run(ssh, f"cd {PROJECT_DIR} && git reset --hard codeup/master 2>&1")
run(ssh, f"cd {PROJECT_DIR} && git clean -fd 2>&1")
run(ssh, f"cd {PROJECT_DIR} && git log --oneline -3")

# 3. ACR login
print("\n--- Step 3: ACR login ---", flush=True)
run(ssh, f"docker login --username {ACR_USER} --password {ACR_PASS} {ACR_REGISTRY}")

# 4. Upload updated docker-compose.prod.yml
print("\n--- Step 4: Upload configs ---", flush=True)
upload(ssh, os.path.join(LOCAL_DEPLOY_DIR, "docker-compose.prod.yml"),
       f"{PROJECT_DIR}/deploy/docker-compose.prod.yml")
upload(ssh, os.path.join(LOCAL_DEPLOY_DIR, "gateway-routes.conf"),
       f"{PROJECT_DIR}/deploy/gateway-routes.conf")

# Generate BUILD_INFO
build_time = time.strftime("%Y-%m-%d_%H:%M:%S_UTC", time.gmtime())
run(ssh, f"echo 'BUILD_TIME={build_time}' > {PROJECT_DIR}/deploy/.env.production")

# 5. Build backend (longest step)
print("\n--- Step 5: Build backend ---", flush=True)
run(ssh, f"cd {PROJECT_DIR}/backend && docker build -f ../deploy/Dockerfile.backend -t {DEPLOY_ID}-backend:latest . 2>&1",
    timeout=600)


# 6. Build admin-web
print("\n--- Step 6: Build admin-web ---", flush=True)
run(ssh, f"cd {PROJECT_DIR}/admin-web && docker build -f ../deploy/Dockerfile.admin -t {DEPLOY_ID}-admin-web:latest . 2>&1",
    timeout=600)

# 7. Build h5-web
print("\n--- Step 7: Build h5-web ---", flush=True)
run(ssh, f"cd {PROJECT_DIR}/h5-web && docker build -f ../deploy/Dockerfile.h5 -t {DEPLOY_ID}-h5-web:latest . 2>&1",
    timeout=600)

# 8. Stop old containers
print("\n--- Step 8: docker compose down ---", flush=True)
run(ssh, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1",
    timeout=60)

# 9. Tag images with ACR names and start
print("\n--- Step 9: Tag and start ---", flush=True)
run(ssh, f"docker tag {DEPLOY_ID}-backend:latest {ACR_REGISTRY}/noob_ai_apps/{DEPLOY_ID}-backend:latest")
run(ssh, f"docker tag {DEPLOY_ID}-admin-web:latest {ACR_REGISTRY}/noob_ai_apps/{DEPLOY_ID}-admin-web:latest")
run(ssh, f"docker tag {DEPLOY_ID}-h5-web:latest {ACR_REGISTRY}/noob_ai_apps/{DEPLOY_ID}-h5-web:latest")
run(ssh, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml up -d 2>&1",
    timeout=60)

# 10. Wait for health checks
print("\n--- Step 10: Wait for healthy ---", flush=True)
for i in range(30):
    time.sleep(10)
    stdin, stdout, stderr = ssh.exec_command(
        f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' | grep -v db",
        timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    out = out.strip()
    unhealthy = [l for l in out.split('\n') if l.strip() and 'healthy' not in l.lower()]
    if not unhealthy:
        print(f"[{i}] All healthy!", flush=True)
        break
    print(f"[{i}] waiting: {unhealthy}", flush=True)
else:
    print("TIMEOUT waiting for health", flush=True)


# 11. Update gateway nginx
print("\n--- Step 11: Update gateway ---", flush=True)
# Copy the server config (overwrite .server file)
run(ssh, f"docker cp {PROJECT_DIR}/deploy/gateway-routes.conf gateway-nginx:/etc/nginx/conf.d/{DEPLOY_ID}.server")
run(ssh, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || echo already_connected")
code, out, err = run(ssh, "docker exec gateway-nginx nginx -t 2>&1")
if "successful" in (out + err).lower() or "syntax is ok" in (out + err).lower():
    run(ssh, "docker exec gateway-nginx nginx -s reload 2>&1")
    print("Nginx reloaded OK", flush=True)
else:
    print("NGINX TEST FAILED!", flush=True)

# 12. Run migrations
print("\n--- Step 12: Database migrations ---", flush=True)
run(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/ 2>/dev/null", timeout=10)
run(ssh, f"docker exec {DEPLOY_ID}-backend sh -c 'for f in /app/migrations/migration_*.py; do echo Running: $f; python3 $f; done' 2>&1",
    timeout=60)

# 13. Default account check
print("\n--- Step 13: Default account check ---", flush=True)
check_cmd = f"docker exec {DEPLOY_ID}-backend python3 -c \"from app.database import engine; from sqlalchemy import text; conn=engine.connect(); rows=conn.execute(text('SELECT username, role FROM users LIMIT 5')).fetchall(); [print(r) for r in rows]\" 2>&1"
run(ssh, check_cmd, timeout=15)

# 14. Final status
print("\n--- Step 14: Final status ---", flush=True)
run(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

print(f"\n===== DEPLOYMENT COMPLETE =====", flush=True)
print(f"URL: https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com", flush=True)
ssh.close()
