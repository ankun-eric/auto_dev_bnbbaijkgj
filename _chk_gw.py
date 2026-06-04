import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
DEPLOY = '6b099ed3-7175-4a78-91f4-44570c84ed27'
_, o, _ = c.exec_command('docker ps --format "{{.Names}}" | grep -i nginx', timeout=20)
print('nginx containers:', o.read().decode())
_, o, _ = c.exec_command(f'docker exec gateway-nginx cat /etc/nginx/conf.d/{DEPLOY}.conf 2>&1 || cat /home/ubuntu/gateway-nginx/conf.d/{DEPLOY}.conf 2>&1', timeout=20)
print('=== gateway conf ===')
print(o.read().decode('utf-8','replace'))
# 直接探查 backend container 自己
_, o, _ = c.exec_command(f'docker exec {DEPLOY}-backend curl -s -o /dev/null -w %{{http_code}} http://localhost:8000/api/admin/home_safety/callback_log', timeout=20)
print('inside backend curl:', o.read().decode())
c.close()
