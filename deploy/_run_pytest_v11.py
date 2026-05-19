"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 远程跑 pytest 验证"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, PORT, USER, PWD, timeout=30, allow_agent=False, look_for_keys=False)
try:
    cmd = (
        f"docker exec {BACKEND_CONTAINER} bash -lc "
        "'cd /app && python -m pytest tests/test_home_config.py -v 2>&1 | tail -60'"
    )
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=600)
    print(o.read().decode("utf-8", errors="replace"))
    es = e.read().decode("utf-8", errors="replace")
    if es.strip():
        print("STDERR:", es[-1000:])
finally:
    c.close()
