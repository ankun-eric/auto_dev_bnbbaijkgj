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

def run(cmd, t=1800):
    print("\n$ " + cmd[:130])
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip()[-3500:])
    if err.strip(): print("[stderr] " + err.strip()[-1500:])
    print("[exit %d]" % code)
    return code

# 重建 h5-web（含新代码，需 no-cache 以确保拉入心率详情页）
run("cd %s && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -30" % DIR, t=2400)
run("cd %s && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -8" % DIR, t=300)
time.sleep(10)
run("docker ps --format '{{.Names}} {{.Status}}' | grep %s" % DEPLOY_ID)
run("docker network connect %s-network %s 2>/dev/null || true" % (DEPLOY_ID, GW))
run("docker exec %s nginx -s reload 2>&1 || true" % GW)
c.close()
print("\n=== REBUILD DONE ===")
