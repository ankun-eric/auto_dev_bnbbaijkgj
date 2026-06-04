import paramiko, time

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=120):
    print(f"  RUN: {cmd[:80]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"  OUT: {out[:200]}")
    if err:
        print(f"  ERR: {err[:200]}")
    return out, err, code

print("=== 安装 Docker ===")

# Step 1: 更新apt并安装依赖
print("\nStep 1: 更新apt和安装依赖...")
cmds = [
    "sudo apt-get update -qq",
    "sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release",
]
for cmd in cmds:
    out, err, code = run(cmd, timeout=120)
    if code != 0 and "W:" not in err:
        print(f"  警告: {err[:200]}")

# Step 2: 添加Docker GPG密钥
print("\nStep 2: 添加Docker GPG密钥...")
run("sudo install -m 0755 -d /etc/apt/keyrings", timeout=10)
run("curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg", timeout=60)
run("sudo chmod a+r /etc/apt/keyrings/docker.gpg", timeout=10)

# Step 3: 添加Docker仓库
print("\nStep 3: 添加Docker仓库...")
arch = "amd64"  # 假设x86_64
run(f'echo "deb [arch={arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null', timeout=30)

# Step 4: 安装Docker
print("\nStep 4: 安装Docker Engine和Compose...")
run("sudo apt-get update -qq", timeout=120)
out, err, code = run("sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin", timeout=300)
if code == 0:
    print("  Docker安装成功")
else:
    print(f"  Docker安装可能有问题: {err[:300]}")

# Step 5: 启动Docker并设置开机启动
print("\nStep 5: 启动Docker...")
run("sudo systemctl enable docker", timeout=30)
run("sudo systemctl start docker", timeout=30)

# Step 6: 添加当前用户到docker组
print("\nStep 6: 添加用户到docker组...")
run("sudo usermod -aG docker ubuntu", timeout=10)

# Step 7: 验证Docker
print("\nStep 7: 验证Docker安装...")
out, err, code = run("sudo docker --version && sudo docker compose version", timeout=30)
print(f"  {out}")

client.close()
print("\n=== Docker安装完成 ===")
