import paramiko

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code

# 预检1: Gateway nginx 配置结构
print("=== 预检1: Gateway nginx 配置结构 ===")
out, err, code = run("cat /home/ubuntu/gateway/nginx.conf 2>/dev/null || echo 'NOT_FOUND'")
if "NOT_FOUND" in out:
    print("Gateway nginx.conf 不存在！需要在生产环境部署gateway-nginx")
else:
    print(out[:2000])

# 预检2: 路由占用检查
print("\n=== 预检2: 路由占用检查 ===")
out, err, code = run("grep -rn 'location\|server_name' /home/ubuntu/gateway/conf.d/ 2>/dev/null || echo 'NO_CONFD'")
print(out[:2000] if out else "无conf.d目录或无路由配置")

# 预检3: Docker 网络拓扑
print("\n=== 预检3: Docker网络拓扑 ===")
out, err, code = run("docker ps -a --filter name=gateway-nginx --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'NO_GATEWAY'")
print(f"Gateway nginx: {out}")
out, err, code = run(f"docker network ls --filter name={DEPLOY_ID}-network --format '{{.Name}}' 2>/dev/null")
print(f"项目网络: {out if out else '无'}")

# 预检4: 磁盘空间检查
print("\n=== 预检4: 磁盘空间检查 ===")
out, err, code = run("df -h / | tail -1")
print(out)

# 额外检查: 项目目录是否存在
print(f"\n=== 项目目录检查 ===")
out, err, code = run(f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>/dev/null | head -10 || echo 'NOT_FOUND'")
print(out[:1000])

# 检查SSL证书
print(f"\n=== SSL证书检查 ===")
out, err, code = run("ls -la /home/ubuntu/gateway/ssl/ 2>/dev/null || echo 'NO_SSL'")
print(out[:1000])

client.close()
