"""诊断 v3：nginx 完整配置 + 直接 curl 容器 3001 端口"""
import paramiko

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
    print(f"\n$ {cmd[:120]}")
    print(f"[rc={rc}]")
    if out: print(out[:3000])
    if err: print("ERR:", err[:500])
    return rc, out, err

# 1. 完整 nginx 配置
run(f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf")

# 2. 容器自检 3001
run(f"docker exec {DEPLOY_ID}-h5 sh -c 'wget -q -S -O - http://127.0.0.1:3001/menu-mode-design-system/index.html 2>&1 | head -10'")
run(f"docker exec {DEPLOY_ID}-h5 sh -c 'wget -q -S -O - http://127.0.0.1:3001/design-system/index.html 2>&1 | head -10'")

# 3. 从 gateway curl h5:3001
run(f"docker exec gateway sh -c 'wget -q -S -O - http://{DEPLOY_ID}-h5:3001/menu-mode-design-system/index.html 2>&1 | head -20'")

ssh.close()
