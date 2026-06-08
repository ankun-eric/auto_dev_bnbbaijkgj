#!/usr/bin/env python3
"""提取前端页面路由路径并输出"""
import paramiko
import re
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=10)

# 获取 h5-web 前端页面路由
stdin, stdout, stderr = ssh.exec_command(
    'find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/src/app -name "page.tsx" -o -name "page.js" 2>/dev/null | sort'
)
pages = stdout.read().decode().strip().split('\n')

base = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/src/app'

print("=== H5-WEB FRONTEND PAGES ===")
for p in pages:
    p = p.strip()
    if not p:
        continue
    rel = p[len(base):] if p.startswith(base) else p
    # 移除 /page.tsx 或 /page.js
    route = re.sub(r'/page\.(tsx|js)$', '', rel)
    if not route:
        route = '/'
    # 将 [param] 替换为 :param
    route = re.sub(r'\[([^\]]+)\]', r':\1', route)
    # 移除路由组 (xxx)
    route = re.sub(r'/\([^)]+\)', '', route)
    if not route:
        route = '/'
    print(f"{route}")

# 获取 admin-web 前端页面路由
stdin2, stdout2, stderr2 = ssh.exec_command(
    'find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/admin-web/src -name "page.tsx" -o -name "page.js" 2>/dev/null | sort'
)
pages2 = stdout2.read().decode().strip().split('\n')

base2 = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/admin-web/src'

print("\n=== ADMIN-WEB FRONTEND PAGES ===")
for p in pages2:
    p = p.strip()
    if not p:
        continue
    rel = p[len(base2):] if p.startswith(base2) else p
    route = re.sub(r'/page\.(tsx|js)$', '', rel)
    if not route:
        route = '/'
    route = re.sub(r'\[([^\]]+)\]', r':\1', route)
    route = re.sub(r'/\([^)]+\)', '', route)
    if not route:
        route = '/'
    print(f"/admin{route}")

ssh.close()
print("\n=== DONE ===")
