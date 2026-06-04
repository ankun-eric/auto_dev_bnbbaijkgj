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

print("=== Docker版本 ===")
out, err, code = run("docker --version && docker compose version")
print(out)

print("\n=== 检查gateway目录 ===")
out, err, code = run("ls -la /home/ubuntu/gateway/ 2>/dev/null || echo 'NO_GATEWAY_DIR'")
print(out[:1000])

print("\n=== 检查nginx镜像 ===")
out, err, code = run("docker images nginx --format '{{.Repository}}:{{.Tag}}' 2>/dev/null")
print(out)

print("\n=== 创建必要目录 ===")
cmds = [
    f"mkdir -p /home/ubuntu/{DEPLOY_ID}/",
    "mkdir -p /home/ubuntu/gateway/conf.d/",
    "mkdir -p /home/ubuntu/gateway/conf.d.bak/",
    "mkdir -p /home/ubuntu/gateway/ssl/",
]
for cmd in cmds:
    out, err, code = run(cmd)
    print(f"  {cmd}: {'OK' if code==0 else f'FAIL({err})'}")

print("\n=== ACR登录 ===")
out, err, code = run("docker login --username=ankun888 --password=xiaobai888 crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com", timeout=30)
print(f"Login: {out}")
if code != 0:
    print(f"ACR登录失败: {err}")

print("\n=== Git clone项目代码 ===")
git_cmd = f"cd /home/ubuntu/{DEPLOY_ID}/ && if [ -d .git ]; then git fetch origin main --depth 1 && git reset --hard origin/main; else git clone --depth 1 --single-branch https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git /home/ubuntu/{DEPLOY_ID}/; fi"
out, err, code = run(git_cmd, timeout=60)
print(f"Git: {out[:500] if out else 'ok'}, err: {err[:500] if err else 'none'}")

client.close()
