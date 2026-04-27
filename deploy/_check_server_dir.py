import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/*.zip",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/",
    "cat /etc/nginx/sites-enabled/* 2>/dev/null || cat /etc/nginx/conf.d/* 2>/dev/null || echo 'checking nginx configs...'",
    "docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null",
    "cat /home/ubuntu/gateway-nginx/conf.d/*.conf 2>/dev/null || echo 'no gateway conf.d'",
    "ls /home/ubuntu/gateway-nginx/ 2>/dev/null || echo 'no gateway-nginx dir'",
]

for cmd in cmds:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

ssh.close()
