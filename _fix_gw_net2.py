import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
DEPLOY = '6b099ed3-7175-4a78-91f4-44570c84ed27'
new_net = f'{DEPLOY}_{DEPLOY}-network'

# 加入 gateway 到新网络
_, o, _ = c.exec_command(f'docker network connect {new_net} gateway-nginx 2>&1', timeout=20)
print('connect:', o.read().decode())

# reload nginx
_, o, _ = c.exec_command('docker exec gateway-nginx nginx -s reload', timeout=20)
print('reload:', o.read().decode())

# 测试
_, o, _ = c.exec_command(f'docker exec gateway-nginx nslookup {DEPLOY}-backend 2>&1 | head -5', timeout=20)
print('nslookup:', o.read().decode())

c.close()
