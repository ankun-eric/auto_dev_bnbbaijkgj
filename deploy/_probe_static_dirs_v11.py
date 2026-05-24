"""探测服务器 static / uploads / nginx 路由"""
import paramiko

HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJ_DIR=f'/home/ubuntu/{DEPLOY_ID}'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)

for d in ['static', 'static/miniprogram', 'uploads', 'uploads/miniprogram']:
    _, o, _ = c.exec_command(f'ls -la {PROJ_DIR}/{d} 2>&1 | head -5')
    print(f'--- {d} ---')
    print(o.read().decode('utf-8', errors='replace'))

_, o, _ = c.exec_command('docker ps --format "{{.Names}}" | head -20')
print('---containers---')
print(o.read().decode('utf-8', errors='replace'))

# locate nginx conf for this project
_, o, _ = c.exec_command(f'sudo find / -name "{DEPLOY_ID}*.conf" 2>/dev/null | head -5')
print('---nginx conf---')
print(o.read().decode('utf-8', errors='replace'))

# fallback: search gateway dir
_, o, _ = c.exec_command(f'ls /home/ubuntu/gateway/conf.d/ 2>/dev/null | head -30')
print('---gateway conf.d---')
print(o.read().decode('utf-8', errors='replace'))

c.close()
