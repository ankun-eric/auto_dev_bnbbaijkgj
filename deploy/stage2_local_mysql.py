import paramiko, time, os

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DEPLOY = r"C:\auto_output\bnbbaijkgj\deploy"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=60):
    print(f"  CMD: {cmd[:150]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 400:
        print(f"  OUT: {out}")
    if err and len(err) > 5:
        print(f"  ERR: {err[:200]}")
    return out, err, code

# Step 1: Modify docker-compose locally to add db service and fix DATABASE_URL
print("=== Step 1: 修改docker-compose.prod.yml ===")
yml_path = os.path.join(LOCAL_DEPLOY, "docker-compose.prod.yml")
with open(yml_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace DATABASE_URL back to local MySQL
old_db_url = "DATABASE_URL: mysql+aiomysql://root:xiaokangaab@gz-cdb-nniq1lmp.sql.tencentcdb.com:27082/bini_health"
new_db_url = "DATABASE_URL: mysql+aiomysql://root:bini_health_2026@6b099ed3-7175-4a78-91f4-44570c84ed27-db:3306/bini_health"
content = content.replace(old_db_url, new_db_url)

# Add db service before backend
db_service = """services:
  db:
    image: mysql:8.0
    container_name: 6b099ed3-7175-4a78-91f4-44570c84ed27-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: bini_health_2026
      MYSQL_DATABASE: bini_health
      MYSQL_CHARSET: utf8mb4
      MYSQL_COLLATION: utf8mb4_unicode_ci
      TZ: UTC
    command: --default-time-zone='+00:00'
    volumes:
      - mysql_data:/var/lib/mysql
      - ./backend/init.sql:/docker-entrypoint-initdb.d/init.sql
    expose:
      - "3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      app-network:
        aliases:
          - 6b099ed3-7175-4a78-91f4-44570c84ed27-db

  backend:"""

content = content.replace("services:\n  backend:", db_service)

# Add depends_on back to backend
old_expose = """    expose:
      - "8000"
    networks:"""
new_expose = """    expose:
      - "8000"
    depends_on:
      db:
        condition: service_healthy
    networks:"""
content = content.replace(old_expose, new_expose)

# Add mysql_data volume
content = content.replace("volumes:\n  uploads_data:", "volumes:\n  mysql_data:\n  uploads_data:")

with open(yml_path, "w", encoding="utf-8") as f:
    f.write(content)
print("  docker-compose.prod.yml updated with db service")

# Step 2: Upload to server
print("\n=== Step 2: 上传更新后的配置 ===")
sftp = client.open_sftp()
sftp.put(yml_path, f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml")
sftp.close()
print("  Uploaded")

# Step 3: Pull mysql:8.0 image
print("\n=== Step 3: 拉取MySQL镜像 ===")
# Try from ACR base
out, err, code = run(f"sudo docker pull crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/mysql:8.0 2>&1", timeout=180)
if code == 0:
    run(f"sudo docker tag crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/mysql:8.0 mysql:8.0", timeout=10)
    print("  MySQL pulled from ACR base")
else:
    print("  MySQL pull failed, trying other...")

# Step 4: Restart all containers
print("\n=== Step 4: 重新部署所有容器 ===")
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=30)
# Create init.sql if needed
init_sql = """CREATE TABLE IF NOT EXISTS _deploy_init (id INT PRIMARY KEY AUTO_INCREMENT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"""
run(f"echo '{init_sql}' | sudo tee /home/ubuntu/{DEPLOY_ID}/backend/init.sql", timeout=10)

out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"  up: {out[:500]}")

# Step 5: Wait for all healthy
print("\n=== Step 5: 等待全部健康 ===")
for i in range(36):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    print(f"  [{i+1}/36] {healthy}/{total} healthy")
    if total >= 4 and healthy >= total:
        print("  全部容器健康!")
        break

# Step 6: Restart gateway and connect
print("\n=== Step 6: 重启Gateway Nginx ===")
run("sudo docker rm -f gateway-nginx 2>/dev/null || true", timeout=10)
run(
    f"sudo docker run -d --name gateway-nginx --restart unless-stopped "
    f"-p 80:80 -p 443:443 "
    f"-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
    f"-v /home/ubuntu/gateway/conf.d/:/etc/nginx/conf.d/:ro "
    f"-v /home/ubuntu/gateway/ssl/:/etc/nginx/ssl/:ro "
    f"nginx:alpine 2>&1",
    timeout=30
)
run(f"sudo docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true", timeout=10)
run("sudo docker exec gateway-nginx nginx -s reload 2>&1", timeout=10)

# Step 7: Test access
print("\n=== Step 7: 验证访问 ===")
time.sleep(3)
out, err, code = run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -5", timeout=20)
print(f"  Root: {out}")
out, err, code = run("curl -sk https://chat.benne-ai.com/api/health 2>&1", timeout=20)
print(f"  /api/health: {out[:300]}")

client.close()
print("\n=== 完成 ===")
