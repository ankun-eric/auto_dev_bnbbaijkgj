import paramiko
import posixpath

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
sftp = client.open_sftp()

# 读取 main.py
path = posixpath.join('/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend', 'app', 'main.py')
with sftp.open(path, 'r') as f:
    content = f.read().decode('utf-8')

lines = content.split('\n')
print(f'Total lines: {len(lines)}')

# 找路由相关行
for i, line in enumerate(lines, 1):
    low = line.lower().strip()
    if 'include_router' in low:
        print(f'INCLUDE_ROUTER {i}: {line.strip()}')
    if low.startswith('@app.'):
        print(f'APP_ROUTE {i}: {line.strip()}')

# 如果没有找到 include_router，打印所有包含 router 的行
found_include = any('include_router' in l.lower() for l in lines)
found_app_route = any(l.strip().lower().startswith('@app.') for l in lines)
print(f'\nHas include_router: {found_include}')
print(f'Has @app routes: {found_app_route}')

# 打印前30行看结构
print('\n=== FIRST 30 LINES ===')
for i, line in enumerate(lines[:30], 1):
    print(f'{i}: {line}')

# 检查路由是如何注册的
print('\n=== Lines with "router" ===')
for i, line in enumerate(lines, 1):
    if 'router' in line.lower():
        print(f'{i}: {line.strip()}')

sftp.close()
client.close()
