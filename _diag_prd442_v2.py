"""诊断 v2：容器端口/nginx 配置"""
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
    if out: print(out[:2000])
    if err: print("ERR:", err[:500])
    return rc, out, err

# 容器网络/端口
run(f"docker inspect {DEPLOY_ID}-h5 --format '{{{{.NetworkSettings.IPAddress}}}} {{{{.HostConfig.PortBindings}}}} {{{{.Config.ExposedPorts}}}}'")
run(f"docker inspect {DEPLOY_ID}-h5 --format '{{{{json .NetworkSettings.Networks}}}}'")

# 容器内监听端口
run(f"docker exec {DEPLOY_ID}-h5 sh -c 'netstat -tln 2>/dev/null || ss -tln 2>/dev/null'")

# 网关 nginx 配置
run("docker exec gateway sh -c 'find /etc/nginx -name \"*.conf\" | head -10'")
run(f"docker exec gateway sh -c 'grep -r \"{DEPLOY_ID}\" /etc/nginx/ 2>/dev/null | head -20'")

# 直接从宿主机 curl 容器
run(f"docker exec gateway sh -c 'wget -q -S -O - http://{DEPLOY_ID}-h5:3000/menu-mode-design-system/index.html 2>&1 | head -20'")
run(f"docker exec gateway sh -c 'wget -q -S -O - http://{DEPLOY_ID}-h5:3000/design-system/index.html 2>&1 | head -10'")

ssh.close()
