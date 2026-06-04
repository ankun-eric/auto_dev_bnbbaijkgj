import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
DEPLOY = '6b099ed3-7175-4a78-91f4-44570c84ed27'

# 在 nginx 容器里 curl
_, o, _ = c.exec_command(f'docker exec gateway-nginx wget -q -O - --tries=1 --timeout=5 http://{DEPLOY}-backend:8000/api/admin/home_safety/callback_log 2>&1 | head -5', timeout=20)
print('nginx -> backend list:', o.read().decode('utf-8','replace'))

# 看 nginx 错误日志
_, o, _ = c.exec_command('docker logs --tail 30 gateway-nginx 2>&1', timeout=20)
print('=== nginx logs ===')
print(o.read().decode('utf-8','replace'))

# 再 reload 一下试试
_, o, _ = c.exec_command('docker exec gateway-nginx nginx -t 2>&1 && docker exec gateway-nginx nginx -s reload 2>&1', timeout=20)
print('reload:', o.read().decode('utf-8','replace'))
c.close()
