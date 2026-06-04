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

# Step 1: Test MySQL with new password
print("=== Step 1: 测试腾讯云MySQL连接（新密码） ===")
out, err, code = run(
    "python3 -c \"import pymysql; "
    "conn = pymysql.connect(host='gz-cdb-nniq1lmp.sql.tencentcdb.com', port=27082, user='root', password='xiaokang989aab'); "
    "print('Connected OK'); conn.close()\" 2>&1",
    timeout=30
)
print(f"  {out}")

if "Connected OK" in out:
    print("  MySQL连接成功!")
    # Create database
    print("\n=== Step 1b: 创建数据库 ===")
    out, err, code = run(
        "python3 -c \"import pymysql; "
        "conn = pymysql.connect(host='gz-cdb-nniq1lmp.sql.tencentcdb.com', port=27082, user='root', password='xiaokang989aab'); "
        "cursor = conn.cursor(); "
        "cursor.execute('CREATE DATABASE IF NOT EXISTS bini_health CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); "
        "print('Database bini_health created/verified'); conn.close()\" 2>&1",
        timeout=30
    )
    print(f"  {out}")
else:
    print("  MySQL连接失败! 检查密码或网络。")
    if "Access denied" in out:
        print("  密码可能仍不正确。")

# Step 2: Upload docker-compose.prod.yml
print("\n=== Step 2: 上传配置 ===")
sftp = client.open_sftp()
sftp.put(os.path.join(LOCAL_DEPLOY, "docker-compose.prod.yml"), f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml")
sftp.close()
print("  Uploaded")

# Step 3: Restart all
print("\n=== Step 3: 重新部署 ===")
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=30)
out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"  up: {out[:500]}")

# Step 4: Wait for health
print("\n=== Step 4: 等待健康检查 ===")
for i in range(30):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    print(f"  [{i+1}/30] {healthy}/{total} healthy")
    if total >= 3 and healthy >= total:
        print("  全部健康!")
        break

# Step 5: Gateway
print("\n=== Step 5: Gateway ===")
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

# Step 6: Test
print("\n=== Step 6: 验证 ===")
time.sleep(3)
out, err, code = run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -5", timeout=20)
print(f"  {out}")
out, err, code = run("curl -sk https://chat.benne-ai.com/api/health 2>&1", timeout=20)
print(f"  /api/health: {out[:300]}")

client.close()
print("\n=== 完成 ===")
