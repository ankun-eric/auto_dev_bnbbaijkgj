import paramiko, os, sys

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_ai_apps"
LOCAL_DEPLOY = r"C:\auto_output\bnbbaijkgj\deploy"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=120):
    print(f"  CMD: {cmd[:120]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 500:
        print(f"  OUT: {out}")
    if err and 'WARNING' not in err and len(err) < 300:
        print(f"  ERR: {err}")
    return out, err, code

# Step 1: Check git clone
print("=== Step 1: 检查Git代码 ===")
out, err, code = run(f"ls /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml /home/ubuntu/{DEPLOY_ID}/.git 2>/dev/null")
if code != 0:
    print("Git clone可能未完成，重新clone...")
    run(f"rm -rf /home/ubuntu/{DEPLOY_ID}/", timeout=10)
    run(f"mkdir -p /home/ubuntu/{DEPLOY_ID}/", timeout=10)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && git clone --depth 1 --single-branch "
        f"https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"
        f"@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git . 2>&1",
        timeout=120
    )
    print(f"Clone result: {out[:300]}")

# Step 2: ACR login
print("\n=== Step 2: ACR登录 ===")
out, err, code = run(f"sudo docker login --username=ankun888 --password=xiaobai888 {ACR}")
print(f"ACR login: {'OK' if 'Login Succeeded' in out else 'FAIL'}")

# Step 3: Upload adapted configs using SFTP
print("\n=== Step 3: 上传配置文件 ===")
sftp = client.open_sftp()
configs = [
    ("docker-compose.prod.yml", f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml"),
    ("gateway-routes.conf", f"/home/ubuntu/{DEPLOY_ID}/gateway-routes.conf"),
    (".env", f"/home/ubuntu/{DEPLOY_ID}/.env"),
]
for local_name, remote_path in configs:
    local_path = os.path.join(LOCAL_DEPLOY, local_name)
    if os.path.exists(local_path):
        sftp.put(local_path, remote_path)
        print(f"  Uploaded {local_name} -> {remote_path}")
    else:
        print(f"  WARNING: {local_name} not found locally")
sftp.close()

# Step 4: Generate self-signed SSL certificate
print("\n=== Step 4: 生成自签名SSL证书 ===")
ssl_cmds = [
    "openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
    "-keyout /home/ubuntu/gateway/ssl/chat.benne-ai.com.key "
    "-out /home/ubuntu/gateway/ssl/chat.benne-ai.com.crt "
    "-subj '/CN=chat.benne-ai.com'",
]
out, err, code = run(ssl_cmds[0], timeout=30)
print(f"SSL cert: {'OK' if code==0 else f'FAIL: {err}'}")

# Step 5: Create gateway nginx main config
print("\n=== Step 5: 创建 Gateway Nginx 主配置 ===")
# Upload nginx.conf via SFTP
sftp = client.open_sftp()
sftp.put(os.path.join(LOCAL_DEPLOY, "nginx_prod.conf"), "/home/ubuntu/gateway/nginx.conf")
sftp.close()
print("  nginx.conf uploaded")

# Step 6: Start gateway-nginx
print("\n=== Step 6: 启动 Gateway Nginx ===")
run("sudo docker pull nginx:alpine 2>&1", timeout=120)
run("sudo docker rm -f gateway-nginx 2>/dev/null || true", timeout=10)
gateway_cmd = (
    "sudo docker run -d --name gateway-nginx --restart unless-stopped "
    "-p 80:80 -p 443:443 "
    "-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
    "-v /home/ubuntu/gateway/conf.d/:/etc/nginx/conf.d/:ro "
    "-v /home/ubuntu/gateway/ssl/:/etc/nginx/ssl/:ro "
    "nginx:alpine"
)
out, err, code = run(gateway_cmd, timeout=30)
print(f"Gateway start: {'OK' if code==0 else f'FAIL: {err}'}")

# Step 7: Create project docker network
print("\n=== Step 7: 创建项目Docker网络 ===")
run(f"sudo docker network rm {DEPLOY_ID}-network 2>/dev/null || true", timeout=10)
out, err, code = run(f"sudo docker network create {DEPLOY_ID}-network", timeout=10)
print(f"Network create: {out}")

# Step 8: Pull images and start containers
print("\n=== Step 8: 拉取镜像并启动容器 ===")
out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml pull 2>&1", timeout=300)
print(f"Pull: {out[:500]}")

# Create .env file with BUILD_COMMIT
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && cp .env .env.production 2>/dev/null || true", timeout=10)

# Stop old containers
run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=60)

# Start containers
print("\n=== 启动容器 ===")
out, err, code = run(f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"Start: {out[:500]}")

# Step 9: Wait for healthchecks
print("\n=== Step 9: 等待健康检查 ===")
import time
for i in range(24):
    time.sleep(5)
    out, err, code = run(
        f"cd /home/ubuntu/{DEPLOY_ID}/ && sudo docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
        timeout=15
    )
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    print(f"  [{i+1}/24] {healthy}/{total} healthy")
    if total > 0 and healthy == total:
        print("  所有容器健康检查通过!")
        break
else:
    print("  警告：等待超时")

client.close()
print("\n=== 部署完成 ===")
