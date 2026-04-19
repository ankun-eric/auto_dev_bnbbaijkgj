import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=60)
for cmd in [
    'grep -n "@router.get" /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend/app/api/products.py',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -n "@router.get" /app/app/api/products.py',
    'docker logs --tail 50 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -50',
]:
    print(f'$ {cmd}')
    si, so, se = c.exec_command(cmd, timeout=60)
    print(so.read().decode())
    err = se.read().decode()
    if err: print('[err]', err)
    print('---')
c.close()
