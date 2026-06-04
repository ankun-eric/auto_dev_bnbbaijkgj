import paramiko, time

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

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

# Step 1: Check container status
print("=== Step 1: 容器状态 ===")
out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps 2>&1")
print(out)

# Step 2: Check unhealthy container logs
print("\n=== Step 2: 检查容器日志 ===")
out, err, code = run(f"sudo docker logs --tail=30 {DEPLOY_ID}-backend 2>&1")
print(f"  Backend: {out[:500]}")

out, err, code = run(f"sudo docker logs --tail=30 {DEPLOY_ID}-admin 2>&1")
print(f"  Admin: {out[:500]}")

out, err, code = run(f"sudo docker logs --tail=30 {DEPLOY_ID}-h5 2>&1")
print(f"  H5: {out[:500]}")

# Step 3: Start gateway-nginx
print("\n=== Step 3: 启动 Gateway Nginx ===")
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

# Step 4: Test and reload nginx
print("\n=== Step 4: 测试并重载 Nginx ===")
out, err, code = run("sudo docker exec gateway-nginx nginx -t 2>&1")
print(f"  Nginx test: {out[:300]}")
if code == 0:
    run("sudo docker exec gateway-nginx nginx -s reload 2>&1")

# Step 5: Connect to network
print("\n=== Step 5: 连接网络 ===")
run(f"sudo docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true", timeout=10)

# Step 6: Recheck container health
print("\n=== Step 6: 再次检查健康 ===")
for i in range(12):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    running = out.count('"running"')
    print(f"  [{i+1}/12] {healthy}/{total} healthy")
    if total > 0 and healthy >= total:
        print("  全部健康!")
        break

# Step 7: Test access
print("\n=== Step 7: 验证访问 ===")
time.sleep(2)
out, err, code = run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -10", timeout=20)
print(f"  Root: {out[:300]}")

out, err, code = run("curl -sk https://chat.benne-ai.com/api/health 2>&1", timeout=20)
print(f"  /api/health: {out[:300]}")

out, err, code = run("curl -sI -k https://chat.benne-ai.com/admin/ 2>&1 | head -5", timeout=20)
print(f"  /admin/: {out[:200]}")

client.close()
print("\n=== 完成 ===")
