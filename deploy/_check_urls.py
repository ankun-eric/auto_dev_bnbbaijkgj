import paramiko
import time

time.sleep(15)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
urls = [
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/orders',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/orders',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/login',
]
for u in urls:
    stdin, stdout, stderr = ssh.exec_command('curl -skI "%s" | head -1' % u, timeout=20)
    print(u[60:], '->', stdout.read().decode().strip())

# 容器内跑 pytest
print('\n=== container pytest ===')
cmd = "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -c 'cd /app && PYTEST_CURRENT_TEST=1 python -m pytest tests/test_merchant_pc_optim_v1_1.py tests/test_payment_config_v1.py tests/test_orders_status_simplification.py -q 2>&1 | tail -5'"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()
