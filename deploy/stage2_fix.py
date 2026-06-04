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
    print(f"  CMD: {cmd[:120]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 300:
        print(f"  OUT: {out}")
    if err and len(err) > 5 and 'WARNING' not in err:
        print(f"  ERR: {err[:200]}")
    return out, err, code

# Step 1: Stop system nginx (port 443 conflict)
print("=== Step 1: 停止系统nginx（端口冲突） ===")
run("sudo systemctl stop nginx 2>/dev/null || true", timeout=10)
run("sudo systemctl disable nginx 2>/dev/null || true", timeout=10)
out, err, code = run("sudo lsof -i :443 2>/dev/null || echo 'no_listener'")
print(f"  Port 443 listeners: {out[:300]}")
out, err, code = run("sudo lsof -i :80 2>/dev/null || echo 'no_listener'")
print(f"  Port 80 listeners: {out[:300]}")

# Step 2: Fix docker-compose.prod.yml network external
print("\n=== Step 2: 修复docker-compose网络配置 ===")
# Read current file
sftp = client.open_sftp()
with sftp.open(f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml", "r") as f:
    content = f.read().decode()
sftp.close()

# Replace network config
old_net = """networks:
  app-network:
    name: 6b099ed3-7175-4a78-91f4-44570c84ed27-network
    driver: bridge"""
new_net = """networks:
  app-network:
    name: 6b099ed3-7175-4a78-91f4-44570c84ed27-network
    external: true"""

content = content.replace(old_net, new_net)
sftp = client.open_sftp()
with sftp.open(f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml", "w") as f:
    f.write(content)
sftp.close()
print("  网络配置已更新为 external: true")

# Also update local copy
local_path = os.path.join(LOCAL_DEPLOY, "docker-compose.prod.yml")
with open(local_path, "w", encoding="utf-8") as f:
    f.write(content)

# Step 3: Clean up old containers and gateway
print("\n=== Step 3: 清理旧容器 ===")
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=30)
run("sudo docker rm -f gateway-nginx 2>/dev/null || true", timeout=10)

# Step 4: Start containers
print("\n=== Step 4: 启动项目容器 ===")
out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"  up output: {out[:500]}")

# Step 5: Wait for containers
print("\n=== Step 5: 等待容器启动 ===")
for i in range(24):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    running = out.count('"running"')
    print(f"  [{i+1}/24] {healthy}/{total} healthy ({running} running)")
    if total > 0 and healthy >= total:
        print("  所有容器健康检查通过!")
        break
    if i >= 2 and total == 0:
        out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml logs --tail=20 2>&1", timeout=15)
        print(f"  Logs: {out[:500]}")
else:
    print("  等待超时")

# Step 6: Start gateway-nginx
print("\n=== Step 6: 启动 Gateway Nginx ===")
out, err, code = run(
    f"sudo docker run -d --name gateway-nginx --restart unless-stopped "
    f"-p 80:80 -p 443:443 "
    f"-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
    f"-v /home/ubuntu/gateway/conf.d/:/etc/nginx/conf.d/:ro "
    f"-v /home/ubuntu/gateway/ssl/:/etc/nginx/ssl/:ro "
    f"nginx:alpine 2>&1",
    timeout=30
)
print(f"  Gateway: {out[:200]}")

# Step 7: Wait for gateway and test
time.sleep(3)
print("\n=== Step 7: 测试 Gateway 配置 ===")
out, err, code = run("sudo docker exec gateway-nginx nginx -t 2>&1")
print(f"  Nginx config test: {out}")
if code == 0:
    run("sudo docker exec gateway-nginx nginx -s reload 2>&1")
    print("  Nginx reloaded")

# Step 8: Connect to network
print("\n=== Step 8: 连接 Gateway 到项目网络 ===")
run(f"sudo docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true", timeout=10)

# Step 9: Test
print("\n=== Step 9: 验证可访问性 ===")
time.sleep(2)
out, err, code = run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -15", timeout=15)
print(f"  {out}")

client.close()
print("\n=== 修复完成 ===")
