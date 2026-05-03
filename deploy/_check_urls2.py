import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

# 安装 pytest 后跑测试
print('=== install pytest in container ===')
stdin, stdout, stderr = ssh.exec_command(
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "bash -c 'pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -3'",
    timeout=300,
)
print(stdout.read().decode('utf-8', errors='replace')[:500])

print('\n=== run pytest in container ===')
stdin, stdout, stderr = ssh.exec_command(
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "bash -c 'cd /app && PYTEST_CURRENT_TEST=1 python -m pytest "
    "tests/test_merchant_pc_optim_v1_1.py tests/test_payment_config_v1.py "
    "tests/test_orders_status_simplification.py "
    "-q --no-header 2>&1 | tail -10'",
    timeout=600,
)
out = stdout.read().decode('utf-8', errors='replace')
print(out)
ssh.close()
