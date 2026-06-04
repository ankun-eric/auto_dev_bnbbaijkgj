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
    print(f"  CMD: {cmd[:130]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 300:
        print(f"  OUT: {out}")
    if err and len(err) > 5 and 'WARNING' not in err:
        print(f"  ERR: {err[:200]}")
    return out, err, code

# Step 1: Stop all
print("=== Step 1: 停止所有容器 ===")
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=30)
run("sudo docker rm -f gateway-nginx 2>/dev/null || true", timeout=10)

# Step 2: Remove old network
print("\n=== Step 2: 删除旧网络 ===")
run(f"sudo docker network rm {DEPLOY_ID}-network 2>/dev/null || true", timeout=10)

# Step 3: Upload latest docker-compose.prod.yml (without external)
print("\n=== Step 3: 上传最新配置 ===")
sftp = client.open_sftp()
local_yml = os.path.join(LOCAL_DEPLOY, "docker-compose.prod.yml")
with open(local_yml, "r", encoding="utf-8") as f:
    content = f.read()
print(f"  Local docker-compose has external: true? {'external: true' in content}")
sftp.put(local_yml, f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml")
sftp.close()
print("  Uploaded docker-compose.prod.yml")

# Step 4: Start containers
print("\n=== Step 4: 启动容器 ===")
out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"  up: {out[:800]}")

# Step 5: Wait for health
print("\n=== Step 5: 等待健康检查 ===")
for i in range(30):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    running = out.count('"running"')
    print(f"  [{i+1}/30] {healthy}/{total} healthy")
    if total > 0 and healthy >= total:
        print("  全部健康!")
        break
    if i >= 3 and total == 0:
        out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml logs --tail=20 2>&1", timeout=15)
        print(f"  Logs: {out[:500]}")

# Step 6: Connect gateway to network
print("\n=== Step 6: 连接Gateway到项目网络 ===")
run(f"sudo docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true", timeout=10)
run("sudo docker exec gateway-nginx nginx -t 2>&1", timeout=15)
run("sudo docker exec gateway-nginx nginx -s reload 2>&1", timeout=10)

# Step 7: Test
print("\n=== Step 7: 验证 ===")
time.sleep(3)
out, err, code = run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -10", timeout=20)
print(f"  {out}")
out, err, code = run("curl -sk https://chat.benne-ai.com/api/health 2>&1", timeout=20)
print(f"  /api/health: {out[:300]}")

client.close()
print("\n=== 完成 ===")
