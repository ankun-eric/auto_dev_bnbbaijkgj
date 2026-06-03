# -*- coding: utf-8 -*-
import paramiko, sys, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = "/home/ubuntu/%s" % DID

def run(c, cmd, timeout=900):
    print("\n$ " + cmd, flush=True)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=True)
    out = ""
    for line in iter(stdout.readline, ""):
        sys.stdout.write(line)
        sys.stdout.flush()
        out += line
    rc = stdout.channel.recv_exit_status()
    print("[exit %d]" % rc, flush=True)
    return rc, out

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

# 1. 拉取最新代码
run(c, "cd %s && timeout 120 git fetch origin master --no-tags 2>&1; git reset --hard origin/master && git log -1 --oneline" % PROJ, timeout=180)

# 2. 重建 H5 容器（仅 h5-web 单服务）
rc, _ = run(c, "cd %s && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -30" % PROJ, timeout=1800)
print("BUILD rc=%d" % rc)
run(c, "cd %s && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10" % PROJ, timeout=300)

# 3. 等待 h5 容器就绪
time.sleep(8)
run(c, "docker ps --format '{{.Names}}\t{{.Status}}' | grep %s" % DID)

# 4. 重连 gateway 网络（保险）
run(c, "docker network connect %s-network gateway-nginx 2>/dev/null; echo done" % DID)
run(c, "docker exec gateway-nginx nginx -s reload 2>&1; echo reloaded")

c.close()
print("\n=== H5 部署完成 ===")
