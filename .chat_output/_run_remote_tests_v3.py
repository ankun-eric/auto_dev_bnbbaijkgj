import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
def run(cmd, t=600):
    stdin,stdout,stderr=ssh.exec_command(cmd, timeout=t)
    code=stdout.channel.recv_exit_status()
    out=stdout.read().decode("utf-8",errors="replace")
    err=stderr.read().decode("utf-8",errors="replace")
    print(f"$ {cmd[:200]}\n  exit={code}")
    if out.strip(): print(f"  out: {out[-1500:]}")
    if err.strip() and code!=0: print(f"  err: {err[-500:]}")
    return code
# 1. 把 tests 目录拷进容器
run("docker cp /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend/tests 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/tests")
# 2. 安装 pytest + httpx + pytest-asyncio + aiosqlite (确保 SQLite test session 可用)
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend pip install -q pytest pytest-asyncio httpx aiosqlite")
# 3. 跑测试
run(("docker exec -e PYTEST_CURRENT_TEST=1 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
     "python -m pytest tests/test_orders_status_simplification.py "
     "tests/test_orders_auto_progress.py tests/test_orders_status_v2.py "
     "tests/test_orders_aftersales_v3.py tests/test_book_after_pay_bugfix.py "
     "--tb=short 2>&1 | tail -25"))
ssh.close()
