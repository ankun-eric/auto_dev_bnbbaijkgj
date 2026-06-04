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

# Step 1: Check if mysql client available and test connection
print("=== Step 1: 测试MySQL连接 ===")
out, err, code = run("which mysql 2>/dev/null || echo 'no_mysql_client'")
print(f"  mysql client: {out}")

# Try connecting via backend container
print("\n=== Step 2: 通过后端容器测试MySQL连接 ===")
out, err, code = run(
    f"sudo docker exec {DEPLOY_ID}-backend python -c \""
    f"import pymysql; "
    f"conn = pymysql.connect(host='{DB_HOST}', port={DB_PORT}, user='{DB_USER}', password='{DB_PASS}'); "
    f"print('Connected OK'); "
    f"conn.close()"
    f"\" 2>&1",
    timeout=20
)
print(f"  Connect test: {out[:500]}")

# Step 3: Check backend full error log
print("\n=== Step 3: 后端完整错误日志 ===")
out, err, code = run(f"sudo docker logs --tail=50 {DEPLOY_ID}-backend 2>&1 | tail -40")
print(f"  Logs: {out[:1000]}")

# Step 4: Check if mysql is reachable from prod server
print("\n=== Step 4: 从生产环境测试MySQL可达性 ===")
out, err, code = run(f"timeout 5 bash -c 'echo > /dev/tcp/{DB_HOST}/{DB_PORT}' 2>&1 && echo 'REACHABLE' || echo 'UNREACHABLE'")
print(f"  MySQL {DB_HOST}:{DB_PORT} is: {out}")

# If MySQL unreachable, fallback to local MySQL container
if "UNREACHABLE" in out:
    print("\n=== 腾讯云MySQL不可达，改用本地MySQL容器 ===")
    # Add db service back to docker-compose
    client.close()
else:
    print("\n=== MySQL可达，检查数据库是否存在 ===")
    # Try creating database via backend container
    out, err, code = run(
        f"sudo docker exec {DEPLOY_ID}-backend python -c \""
        f"import pymysql; "
        f"conn = pymysql.connect(host='{DB_HOST}', port={DB_PORT}, user='{DB_USER}', password='{DB_PASS}'); "
        f"cursor = conn.cursor(); "
        f"cursor.execute('CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); "
        f"print('Database OK'); "
        f"conn.close()"
        f"\" 2>&1",
        timeout=20
    )
    print(f"  Create DB: {out[:500]}")

client.close()
