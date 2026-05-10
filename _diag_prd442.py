"""快速诊断：直接 SSH 到服务器查看 nginx 路由和容器内文件 + curl 直击容器"""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"\n$ {cmd}")
    print(f"[rc={rc}]")
    if out: print("STDOUT:", out)
    if err: print("STDERR:", err)
    return rc, out, err

# 1. 容器内直接 curl 自身（验证 Next.js 是否能 serve 新静态文件）
run(f"docker exec {DEPLOY_ID}-h5 sh -c 'wget -q -O - http://127.0.0.1:3000/menu-mode-design-system/index.html | head -5'")

# 2. 与 design-system 对比
run(f"docker exec {DEPLOY_ID}-h5 sh -c 'wget -q -O - http://127.0.0.1:3000/design-system/index.html | head -5'")

# 3. 容器内文件确认 + 权限
run(f"docker exec {DEPLOY_ID}-h5 ls -la /app/public/menu-mode-design-system/")

# 4. 网关 nginx 配置（看是否路由到 h5）
run(f"docker ps --format '{{{{.Names}}}}' | grep -E 'nginx|gateway|traefik'")

# 5. h5 进程
run(f"docker exec {DEPLOY_ID}-h5 sh -c 'ps aux | head -10'")

ssh.close()
