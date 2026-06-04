import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

base = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

paths = ['/h5/', '/h5/login/', '/h5/login', '/api/health', '/api/chat/sessions']
for p in paths:
    _, o, _ = c.exec_command(f"curl -s -o /dev/null -w 'GET {p} HTTP %{{http_code}}\\n' '{base}{p}'")
    print(o.read().decode().strip())

print("\n--- h5 logs (last 40 lines) ---")
_, o, _ = c.exec_command('docker logs --tail 40 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 2>&1')
print(o.read().decode()[:5000])

print("\n--- backend logs (last 20) ---")
_, o, _ = c.exec_command('docker logs --tail 20 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1')
print(o.read().decode()[:3000])

print("\n--- h5 容器内文件 ---")
_, o, _ = c.exec_command("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ls /app/.next/server/app 2>&1 | head -30")
print(o.read().decode())
c.close()
