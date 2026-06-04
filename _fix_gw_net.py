import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
DEPLOY = '6b099ed3-7175-4a78-91f4-44570c84ed27'

# 查看网络
_, o, _ = c.exec_command('docker network ls', timeout=20)
print(o.read().decode())

# 看看 gateway-nginx 加入了哪些网络
_, o, _ = c.exec_command('docker inspect gateway-nginx -f "{{json .NetworkSettings.Networks}}"', timeout=20)
print('gateway nets:', o.read().decode())

# 看 backend 在哪些网络
_, o, _ = c.exec_command(f'docker inspect {DEPLOY}-backend -f "{{{{json .NetworkSettings.Networks}}}}"', timeout=20)
print('backend nets:', o.read().decode())

# 把 gateway 加入项目网络（如果没加）
project_net = f'{DEPLOY}_default'
_, o, _ = c.exec_command(f'docker network connect {project_net} gateway-nginx 2>&1 || echo already', timeout=20)
print('connect:', o.read().decode())

# reload nginx
_, o, _ = c.exec_command('docker exec gateway-nginx nginx -s reload', timeout=20)
print('reload:', o.read().decode())
c.close()
