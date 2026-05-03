import paramiko, sys
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
cmd = (
    "docker exec -e PYTEST_CURRENT_TEST=1 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "python -m pytest tests/test_orders_status_simplification.py "
    "tests/test_orders_auto_progress.py tests/test_orders_status_v2.py "
    "tests/test_orders_aftersales_v3.py tests/test_book_after_pay_bugfix.py "
    "--tb=short 2>&1 | tail -30"
)
print("$ " + cmd[:200])
stdin,stdout,stderr=ssh.exec_command(cmd, timeout=600)
code=stdout.channel.recv_exit_status()
print("exit:", code)
print(stdout.read().decode("utf-8", errors="replace"))
print("STDERR:", stderr.read().decode("utf-8", errors="replace")[-500:])
ssh.close()
