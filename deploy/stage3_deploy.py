"""
阶段 3：远程部署脚本
- Git 拉取最新代码
- 上传更新后的配置文件
- Docker 构建 + 启动
- Gateway 配置更新
- 数据库迁移
- 默认账号检查
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
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_SERVER = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
CODEUP_REPO = f"https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
CODEUP_USER = "kun-an"
CODEUP_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

LOCAL_DEPLOY_DIR = os.path.dirname(os.path.abspath(__file__))

def run(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd[:100]}")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if exit_code != 0:
        print(f"EXIT: {exit_code}")
    if out:
        print(out[:800])
    if err and exit_code != 0:
        print("STDERR:", err[:300])
    return exit_code, out, err

def upload_file(ssh, local_path, remote_path):
    """Upload a file via SFTP."""
    print(f"\n>>> UPLOAD {local_path} -> {remote_path}")
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("UPLOAD OK")


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
print(f"=== STAGE 3: DEPLOY {DEPLOY_ID} ===")

# Step 1: Check existing state
print("\n--- Step 1: Check existing state ---")
run(ssh, f"ls {PROJECT_DIR}/.git/config 2>/dev/null && echo GIT_EXISTS || echo NO_GIT")
run(ssh, f"docker ps -a --filter name={DEPLOY_ID} --format '{{.Names}} {{.Status}}'")

# Step 2: ACR login
print("\n--- Step 2: ACR login ---")
code, out, err = run(ssh, f"docker login --username {ACR_USER} --password {ACR_PASS} {ACR_REGISTRY}")
if "Login Succeeded" not in out:
    print("WARNING: ACR login may have failed")

# Step 3: Git pull latest code
print("\n--- Step 3: Git fetch latest code ---")
# Configure git remote with token
git_url_with_token = CODEUP_REPO.replace("https://", f"https://{CODEUP_USER}:{CODEUP_TOKEN}@")
run(ssh, f"cd {PROJECT_DIR} && git remote set-url codeup {git_url_with_token}")
run(ssh, f"cd {PROJECT_DIR} && git fetch codeup master --depth=1 2>&1")
run(ssh, f"cd {PROJECT_DIR} && git reset --hard codeup/master 2>&1")
run(ssh, f"cd {PROJECT_DIR} && git log --oneline -1")

# Step 4: Upload updated docker-compose.prod.yml and gateway configs
print("\n--- Step 4: Upload updated configs ---")
upload_file(ssh, os.path.join(LOCAL_DEPLOY_DIR, "docker-compose.prod.yml"),
            f"{PROJECT_DIR}/deploy/docker-compose.prod.yml")

# Generate BUILD_INFO
build_time = time.strftime("%Y-%m-%d_%H:%M:%S_UTC", time.gmtime())
run(ssh, f"echo 'BUILD_TIME={build_time}' > {PROJECT_DIR}/deploy/.env.production")
run(ssh, f"echo 'DEPLOY_ID={DEPLOY_ID}' >> {PROJECT_DIR}/deploy/.env.production")


# Step 5: Build and deploy
print("\n--- Step 5: Docker compose build + up ---")
run(ssh, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml build --no-cache 2>&1",
    timeout=600)
run(ssh, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1",
    timeout=60)
run(ssh, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml up -d 2>&1",
    timeout=120)

# Step 6: Wait for health checks
print("\n--- Step 6: Wait for containers healthy ---")
for i in range(24):
    time.sleep(10)
    code, out, err = run(ssh,
        f"docker ps -a --filter name={DEPLOY_ID} --format '{{.Names}} {{.Status}}' | grep -v db",
        timeout=10)
    lines = out.strip().split('\n')
    unhealthy = [l for l in lines if 'healthy' not in l.lower() and l.strip()]
    if not unhealthy:
        print(f"[{i}] All containers healthy!")
        break
    print(f"[{i}] Waiting... unhealthy: {unhealthy}")
else:
    print("WARNING: Not all containers became healthy within timeout")
    run(ssh, f"docker ps -a --filter name={DEPLOY_ID}")

# Step 7: Update gateway nginx
print("\n--- Step 7: Update gateway nginx ---")
# Backup existing
run(ssh, f"docker exec gateway-nginx cp /etc/nginx/conf.d/{DEPLOY_ID}.server /etc/nginx/conf.d/{DEPLOY_ID}.server.bak.{int(time.time())} 2>/dev/null || echo NO_BACKUP_NEEDED")
# Copy new server config to gateway container
run(ssh, f"docker cp {PROJECT_DIR}/deploy/gateway-routes.conf gateway-nginx:/etc/nginx/conf.d/{DEPLOY_ID}.server")
# Ensure gateway is on project network
run(ssh, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || echo ALREADY_CONNECTED")
# Test nginx config
code, out, err = run(ssh, "docker exec gateway-nginx nginx -t 2>&1")
if "successful" in (out + err).lower():
    run(ssh, "docker exec gateway-nginx nginx -s reload 2>&1")
    print("Nginx reloaded successfully")
else:
    print("NGINX TEST FAILED, rolling back...")
    run(ssh, f"docker exec gateway-nginx cp /etc/nginx/conf.d/{DEPLOY_ID}.server.bak.{int(time.time())} /etc/nginx/conf.d/{DEPLOY_ID}.server 2>/dev/null")
    run(ssh, "docker exec gateway-nginx nginx -s reload 2>&1")


# Step 8: Run database migrations
print("\n--- Step 8: Database migrations ---")
run(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/ 2>/dev/null | head -10",
    timeout=10)
run(ssh, f"docker exec {DEPLOY_ID}-backend python -c \"import sys; sys.path.insert(0,'/app'); from app.database import engine; print('DB connection OK')\" 2>&1",
    timeout=15)
# Run incremental migration scripts
run(ssh, f"docker exec {DEPLOY_ID}-backend sh -c 'for f in /app/migrations/migration_*.py; do echo \"Running: \$f\"; python \"\$f\"; done' 2>&1",
    timeout=60)

# Step 9: Default account check
print("\n--- Step 9: Default account check ---")
check_sql = "SELECT username, role FROM users WHERE username IN ('admin', 'admin123') LIMIT 5;"
run(ssh, f"docker exec {DEPLOY_ID}-db mysql -uroot -pxiaokang989aab bini_health -e \"{check_sql}\" 2>&1",
    timeout=10)

# Step 10: Final verification
print("\n--- Step 10: Final verification ---")
run(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{.Names}}\t{{.Status}}'")
run(ssh, f"docker exec gateway-nginx nginx -T 2>&1 | grep -A2 'server_name.*{DEPLOY_ID[:8]}' | head -10",
    timeout=10)

print("\n===== DEPLOYMENT COMPLETED =====")
print(f"URL: https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com")
ssh.close()
