import paramiko

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=120):
    print(f"  RUN: {cmd[:100]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    # Read in chunks
    out_parts = []
    err_parts = []
    import select
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            out_parts.append(stdout.channel.recv(1024).decode(errors='replace'))
        if stderr.channel.recv_stderr_ready():
            err_parts.append(stderr.channel.recv_stderr(1024).decode(errors='replace'))
    # Drain remaining
    import time
    time.sleep(0.5)
    try:
        while stdout.channel.recv_ready():
            out_parts.append(stdout.channel.recv(4096).decode(errors='replace'))
        while stderr.channel.recv_stderr_ready():
            err_parts.append(stderr.channel.recv_stderr(4096).decode(errors='replace'))
    except:
        pass
    out = ''.join(out_parts).strip()
    err = ''.join(err_parts).strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"  OUT: {out[:300]}")
    if err and 'WARNING' not in err:
        print(f"  ERR: {err[:300]}")
    return out, err, code

print("=== 使用阿里云镜像安装Docker ===")

# 方案: 直接从阿里云镜像下载并安装Docker

# Step 1: 清理之前失败的配置
print("\nStep 1: 清理...")
run("sudo rm -f /etc/apt/sources.list.d/docker.list", timeout=10)
run("sudo rm -f /etc/apt/keyrings/docker.gpg", timeout=10)

# Step 2: 使用阿里云Docker源
print("\nStep 2: 配置阿里云Docker源...")
cmds = [
    "curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
    "sudo chmod a+r /etc/apt/keyrings/docker.gpg",
    'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
]
for cmd in cmds:
    out, err, code = run(cmd, timeout=60)

# Step 3: 更新apt并安装Docker
print("\nStep 3: 安装Docker...")
out, err, code = run("sudo apt-get update -qq 2>&1", timeout=120)
out, err, code = run("sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>&1", timeout=300)

# Step 4: 启动Docker
print("\nStep 4: 启动Docker...")
run("sudo systemctl enable docker 2>&1", timeout=30)
run("sudo systemctl start docker 2>&1", timeout=30)
run("sudo usermod -aG docker ubuntu 2>&1", timeout=10)

# Step 5: 配置Docker镜像加速器
print("\nStep 5: 配置镜像加速器...")
run("sudo mkdir -p /etc/docker", timeout=10)
daemon_config = '{"registry-mirrors": ["https://registry.cn-hangzhou.aliyuncs.com"],"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"}}'
run(f"echo '{daemon_config}' | sudo tee /etc/docker/daemon.json", timeout=10)
run("sudo systemctl restart docker 2>&1", timeout=30)

# Step 6: 验证
print("\nStep 6: 验证Docker...")
out, err, code = run("sudo docker --version", timeout=10)
print(f"  Docker version: {out}")
out, err, code = run("sudo docker compose version", timeout=10)
print(f"  Compose version: {out}")

client.close()
print("\n=== Docker安装完成 ===")
