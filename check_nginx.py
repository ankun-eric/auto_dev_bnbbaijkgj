import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Bangbang987", timeout=30)

cmds = [
    'docker ps --format "table {{.Names}}\t{{.Ports}}" 2>/dev/null | head -20',
    "ls /etc/nginx/conf.d/ 2>/dev/null",
    "cat /etc/nginx/conf.d/gateway-routes.conf 2>/dev/null | head -80",
    "docker exec gateway-nginx cat /etc/nginx/conf.d/gateway-routes.conf 2>/dev/null | head -100",
    "docker exec gateway-nginx cat /etc/nginx/nginx.conf 2>/dev/null | head -60",
]
for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")
ssh.close()
