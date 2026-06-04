import paramiko

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DB_HOST = "gz-cdb-nniq1lmp.sql.tencentcdb.com"
DB_PORT = "27082"
DB_USER = "root"
DB_PASS = "xiaokangaab"
DB_NAME = "bini_health"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=60):
    print(f"  CMD: {cmd[:130]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 300:
        print(f"  OUT: {out}")
    if err and len(err) > 5:
        print(f"  ERR: {err[:200]}")
    return out, err, code

# Step 1: Stop backend container
print("=== Step 1: 停止后端容器 ===")
run(f"sudo docker stop {DEPLOY_ID}-backend 2>/dev/null || true", timeout=20)

# Step 2: Install python mysql client on host
print("\n=== Step 2: 安装Python MySQL客户端 ===")
out, err, code = run("pip3 install pymysql 2>&1 | tail -3", timeout=60)
print(f"  {out}")

# Step 3: Test MySQL connection
print("\n=== Step 3: 测试MySQL连接 ===")
out, err, code = run(
    f"python3 -c \"import pymysql; "
    f"conn = pymysql.connect(host='{DB_HOST}', port={DB_PORT}, user='{DB_USER}', password='{DB_PASS}'); "
    f"print('Connected OK'); conn.close()\" 2>&1",
    timeout=30
)
print(f"  Connection: {out}")
if "Access denied" in out or "Error" in out:
    print("  MySQL认证失败！")

# Step 4: Create database if connection works
print("\n=== Step 4: 创建数据库 ===")
out, err, code = run(
    f"python3 -c \"import pymysql; "
    f"conn = pymysql.connect(host='{DB_HOST}', port={DB_PORT}, user='{DB_USER}', password='{DB_PASS}'); "
    f"cursor = conn.cursor(); "
    f"cursor.execute('CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); "
    f"cursor.execute('SHOW DATABASES'); "
    f"dbs = [r[0] for r in cursor.fetchall()]; "
    f"print('Databases:', dbs); "
    f"conn.close()\" 2>&1",
    timeout=30
)
print(f"  Create DB: {out}")

# Step 5: Restart backend
print("\n=== Step 5: 重启后端容器 ===")
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d backend 2>&1", timeout=30)

# Step 6: Wait for backend health
print("\n=== Step 6: 等待后端健康 ===")
import time
for i in range(12):
    time.sleep(5)
    out, err, code = run(
        f"sudo docker ps --filter name={DEPLOY_ID}-backend --format '{{{{.Status}}}}'",
        timeout=15
    )
    print(f"  [{i+1}/12] Status: {out}")
    if out and "healthy" in out.lower():
        print("  后端健康!")
        break
    if "restarting" in out.lower() and i >= 3:
        out, err, code = run(f"sudo docker logs --tail=10 {DEPLOY_ID}-backend 2>&1")
        print(f"  最新日志: {out[:300]}")

client.close()
print("\n=== 数据库诊断完成 ===")
