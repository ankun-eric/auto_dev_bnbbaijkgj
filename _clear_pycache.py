import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASSWORD='Newbang888'
REMOTE_BASE='/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
cmd = (
    f"cd {REMOTE_BASE} && docker compose exec -T backend "
    "find /app/tests -name '__pycache__' -exec rm -rf {} + 2>/dev/null; "
    "echo cleared"
)
_, o, _ = c.exec_command(cmd, timeout=60)
print(o.read().decode("utf-8","replace"))

# 重新跑指定测试
cmd = (
    f"cd {REMOTE_BASE} && docker compose exec -T backend "
    "python -m pytest tests/test_home_safety_v2_revision.py::test_push_success_with_code_200_message_success "
    "--tb=long 2>&1 > /tmp/o.txt; "
    "grep -B2 -A6 '\u7f3a\u5c11' /tmp/o.txt; echo === DONE ==="
)
_, o, _ = c.exec_command(cmd, timeout=120)
print(o.read().decode("utf-8","replace"))
c.close()
