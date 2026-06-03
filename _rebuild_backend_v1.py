"""[BUGFIX] 重新 build backend 镜像并替换"""
import paramiko, time
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"/home/ubuntu/{ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd, timeout=900):
    print("$", cmd)
    i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = o.channel.recv_exit_status()
    print(o.read().decode("utf-8", errors="replace"))
    er = e.read().decode("utf-8", errors="replace")
    if er.strip():
        print("[stderr]", er)
    return rc

run(f"cd {BASE} && docker compose build backend 2>&1 | tail -40", timeout=900)
run(f"cd {BASE} && docker compose up -d backend 2>&1 | tail -10", timeout=300)
time.sleep(10)
run(f"docker exec {ID}-backend grep -c 'isoformat() + ' /app/app/api/home_safety_v1.py")
run(f"docker exec {ID}-backend grep -c 'isoformat() + ' /app/tests/test_home_safety_v1.py")
c.close()
