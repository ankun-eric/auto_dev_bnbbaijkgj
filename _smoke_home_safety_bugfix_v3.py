"""[BUGFIX] 服务器端冒烟测试 v3: 安装 aiosqlite 后跑"""
import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONT = f"{ID}-backend"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

cmds = [
    f"docker exec {CONT} pip install aiosqlite -i https://mirrors.cloud.tencent.com/pypi/simple --quiet 2>&1 | tail -3",
    f"docker exec {CONT} sh -c 'cd /app && python -m pytest tests/test_home_safety_v1.py -v --tb=short --no-header 2>&1' | tail -80",
]
for cmd in cmds:
    print("$", cmd)
    i, o, e = c.exec_command(cmd, timeout=600, get_pty=False)
    print(o.read().decode("utf-8", errors="replace"))
    er = e.read().decode("utf-8", errors="replace")
    if er.strip():
        print("[stderr]", er)
c.close()
