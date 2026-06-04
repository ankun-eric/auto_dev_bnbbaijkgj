import paramiko, time

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_ai_apps"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=120):
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

# Step 1: Deploy gateway-routes.conf to gateway
print("=== Step 1: 部署 Gateway 路由配置 ===")
run(f"sudo cp /home/ubuntu/{DEPLOY_ID}/gateway-routes.conf /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf")

# Step 2: Start gateway-nginx
print("\n=== Step 2: 启动 Gateway Nginx ===")
run("sudo docker rm -f gateway-nginx 2>/dev/null || true", timeout=10)
gw_cmd = (
    f"sudo docker run -d --name gateway-nginx --restart unless-stopped "
    f"-p 80:80 -p 443:443 "
    f"-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
    f"-v /home/ubuntu/gateway/conf.d/:/etc/nginx/conf.d/:ro "
    f"-v /home/ubuntu/gateway/ssl/:/etc/nginx/ssl/:ro "
    f"nginx:alpine"
)
out, err, code = run(gw_cmd, timeout=30)
print(f"  Gateway start: {'OK' if code==0 else f'FAIL'}")

# Step 3: Test nginx config
print("\n=== Step 3: 测试 Nginx 配置 ===")
out, err, code = run("sudo docker exec gateway-nginx nginx -t 2>&1", timeout=15)
print(f"  Nginx test: {out}")
if code != 0:
    print("  Nginx配置测试失败！检查配置...")
    out, err, code = run("sudo docker exec gateway-nginx cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>&1")
    print(f"  Config content: {out[:500]}")

# Step 4: Create docker network
print("\n=== Step 4: 创建项目网络 ===")
run(f"sudo docker network rm {DEPLOY_ID}-network 2>/dev/null || true", timeout=10)
out, err, code = run(f"sudo docker network create {DEPLOY_ID}-network", timeout=10)

# Step 5: Pull project images
print("\n=== Step 5: 拉取项目镜像 ===")
images = ["backend", "admin-web", "h5-web"]
for img in images:
    tag = f"{ACR}/{ACR_NS}/{DEPLOY_ID}-{img}:latest"
    print(f"  Pulling {tag}...")
    out, err, code = run(f"sudo docker pull {tag} 2>&1", timeout=180)
    if code == 0:
        print(f"  Pulled {img} OK")
    else:
        print(f"  Pull FAILED for {img}: {err[:200]}")

# Step 6: Stop old containers and start new ones
print("\n=== Step 6: 停止旧容器并启动新容器 ===")
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=60)

# Create env
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && echo 'BUILD_COMMIT=publish-$(date +%Y%m%d%H%M%S)' > .env", timeout=10)

out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"  Start output: {out[:500]}")

# Step 7: Wait for health
print("\n=== Step 7: 等待健康检查 ===")
all_healthy = False
for i in range(36):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    running = out.count('"running"')
    print(f"  [{i+1}/36] {healthy}/{total} healthy ({running} running)")
    if total > 0 and healthy >= total:
        print("  所有容器健康检查通过!")
        all_healthy = True
        break
    # Check logs if not starting
    if total == 0 and i >= 3:
        print("  容器未启动, 检查日志...")
        out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml logs --tail=20 2>&1", timeout=15)
        print(f"  Logs: {out[:500]}")

if not all_healthy:
    print("  等待超时, 检查状态...")
    out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps 2>&1")
    print(out)

# Step 8: Connect gateway to network
print("\n=== Step 8: 连接 Gateway 到项目网络 ===")
run(f"sudo docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true", timeout=10)
out, err, code = run(f"sudo docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'")
print(f"  网络中的容器: {out}")

# Step 9: Reload nginx
print("\n=== Step 9: 重载 Nginx ===")
out, err, code = run("sudo docker exec gateway-nginx nginx -t 2>&1")
print(f"  Nginx test: {out}")
if code == 0:
    run("sudo docker exec gateway-nginx nginx -s reload 2>&1")
    print("  Nginx reloaded")

# Step 10: Verify accessibility
print("\n=== Step 10: 验证可访问性 ===")
time.sleep(2)
out, err, code = run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -10", timeout=15)
print(f"  curl result: {out[:500]}")

client.close()
print("\n=== 部署流程完成 ===")
