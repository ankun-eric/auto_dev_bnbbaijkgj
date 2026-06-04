import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

# 用宿主 curl 跨 docker 内网，先看 h5 容器IP
_, o, _ = c.exec_command('docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 --format "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"')
h5_ip = o.read().decode().strip()
print(f"H5 IP: {h5_ip}")

ip = h5_ip.split()[0] if h5_ip.split() else h5_ip
for p in ['/h5', '/h5/', '/h5/ai-home', '/h5/login', '/ai-home', '/']:
    _, o, _ = c.exec_command(f"curl -s -o /dev/null -w '{p} HTTP %{{http_code}}\\n' http://{ip}:3001{p}")
    print(o.read().decode().strip())

# 看 next.config
print("\n--- next config ---")
_, o, _ = c.exec_command("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 cat /app/next.config.js 2>&1 | head -40 || docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 cat /app/next.config.mjs 2>&1 | head -40")
print(o.read().decode())

c.close()
