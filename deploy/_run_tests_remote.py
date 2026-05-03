import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

PROJ = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
CN = '6b099ed3-7175-4a78-91f4-44570c84ed27-backend'

print('Wait for backend to be ready ...')
time.sleep(15)

cmds = [
    f"docker logs --tail 50 {CN} 2>&1",
    f"docker cp {PROJ}/backend/tests/test_orders_auto_progress.py {CN}:/app/tests/",
    f"docker exec -e PYTEST_CURRENT_TEST=1 {CN} python -m pytest tests/test_orders_auto_progress.py -v --tb=short",
    f"docker exec -e PYTEST_CURRENT_TEST=1 {CN} python -m pytest tests/test_orders_status_v2.py tests/test_orders_aftersales_v3.py -v --tb=short -q",
]
for cmd in cmds:
    print('=' * 70)
    print('CMD:', cmd[:200])
    _, o, e = ssh.exec_command(cmd, timeout=600)
    out = o.read().decode('utf-8', errors='replace')
    err = e.read().decode('utf-8', errors='replace')
    # 输出主要内容
    print(out[:8000])
    if err.strip():
        print('--- ERR ---')
        print(err[:1500])

ssh.close()
