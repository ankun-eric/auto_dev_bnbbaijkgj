import paramiko, sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888')

D = '6b099ed3-7175-4a78-91f4-44570c84ed27'
DOM = f'{D}.noob-ai.test.bangbangvip.com'

print('=== 最终部署验证 ===')

# Containers
s,o,e = c.exec_command(f'docker ps --filter name={D} --format "table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"')
print('[容器状态]')
print(o.read().decode())

# HTTP tests
for path, name in [('/', 'H5首页'), ('/api/health', 'API健康'), ('/admin/', 'Admin后台')]:
    s,o,e = c.exec_command(f'curl -sk -o /dev/null -w "%{{http_code}}" https://{DOM}{path}')
    code = o.read().decode().strip()
    print(f'[{name}] https://{DOM}{path} -> HTTP {code}')

# nginx test
s,o,e = c.exec_command('docker exec gateway-nginx nginx -t 2>&1 | tail -5')
print('\n[Gateway Config]')
print(o.read().decode())

c.close()
print('\n验证完成')
