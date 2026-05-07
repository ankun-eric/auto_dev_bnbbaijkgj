"""Bug401 admin-web 重建部署"""
import paramiko, sys, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR=f"/home/ubuntu/{DID}"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, timeout=900, hide=False):
    print(f"\n>>> {cmd}")
    chan=c.get_transport().open_session(); chan.settimeout(timeout); chan.get_pty(); chan.exec_command(cmd)
    buf=b""; last=time.time()
    while True:
        if chan.recv_ready():
            d=chan.recv(65535); buf+=d
            try: print(d.decode("utf-8",errors="ignore"),end="",flush=True)
            except: pass
            last=time.time()
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        if time.time()-last>timeout:
            print("[TIMEOUT]"); break
        time.sleep(0.3)
    rc=chan.recv_exit_status()
    print(f"\n[rc={rc}]")
    return rc, buf.decode("utf-8",errors="ignore")

# 1. 检查项目目录
run(f"cd {PROJ_DIR} && pwd && git remote -v && git log -1 --oneline")

# 2. 拉取最新代码
run(f"cd {PROJ_DIR} && git fetch origin && git reset --hard origin/master && git log -1 --oneline")

# 3. 看 docker-compose 配置以确定 admin 服务名
run(f"ls {PROJ_DIR}/*.yml {PROJ_DIR}/docker-compose* 2>/dev/null")
run(f"cat {PROJ_DIR}/docker-compose.yml 2>/dev/null | head -120")

c.close()
