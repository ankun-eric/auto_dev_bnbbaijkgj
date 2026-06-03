"""rebuild backend image from sftp 同步过去的宿主机源码"""
import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASSWORD='Newbang888'
REMOTE_BASE='/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

cmd = f"cd {REMOTE_BASE} && docker compose up -d --build backend 2>&1 | tail -20"
print("$", cmd)
_, o, _ = c.exec_command(cmd, timeout=600)
print(o.read().decode("utf-8","replace"))

# wait
import time
time.sleep(15)

# 安装 pytest
cmd = "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend pip install pytest pytest-asyncio aiosqlite 2>&1 | tail -3"
_, o, _ = c.exec_command(cmd, timeout=180); print(o.read().decode("utf-8","replace"))

# 跑测试 - 仅看失败摘要 + 详情
cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "python -m pytest tests/test_home_safety_v1.py tests/test_home_safety_v2_revision.py "
    "--tb=long 2>&1 > /tmp/pytest_out.txt; "
    "grep -B1 -A25 'FAILED\\|Error\\|assert' /tmp/pytest_out.txt | head -300; "
    "echo === SUMMARY ===; "
    "tail -25 /tmp/pytest_out.txt"
)
print("$", cmd)
_, o, _ = c.exec_command(cmd, timeout=600); print(o.read().decode("utf-8","replace"))
c.close()
