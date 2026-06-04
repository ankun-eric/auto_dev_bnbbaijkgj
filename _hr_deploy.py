import paramiko, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DIR = "/home/ubuntu/%s" % DEPLOY_ID
GW = "gateway-nginx"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=900, echo=True):
    if echo:
        print("\n$ " + cmd)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t, get_pty=False)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-4000:])
    if err.strip():
        print("[stderr] " + err.strip()[-2000:])
    print("[exit %d]" % code)
    return code, out, err

# 1. 拉取最新代码
run("cd %s && timeout 40 git fetch origin --no-tags 2>&1 || echo FETCH_FAIL" % DIR)
run("cd %s && git reset --hard origin/master && git log -1 --oneline" % DIR)

# 2. 重建 h5-web 容器（仅 H5 改动）
run("cd %s && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -25" % DIR, t=1800)
run("cd %s && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10" % DIR, t=300)

# 3. 等待容器就绪
time.sleep(8)
run("docker ps --format '{{.Names}} {{.Status}}' | grep %s" % DEPLOY_ID)

# 4. 重新连接 gateway 网络（双保险）
run("docker network connect %s-network %s 2>/dev/null || true" % (DEPLOY_ID, GW))
run("docker exec %s nginx -t 2>&1" % GW)
run("docker exec %s nginx -s reload 2>&1 || true" % GW)

c.close()
print("\n=== DEPLOY DONE ===")
