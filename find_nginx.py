import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Bangbang987', timeout=30)
cmds = [
    'sudo docker ps --filter name=gateway --format "{{.Names}}"',
    'sudo docker ps --filter name=nginx --format "{{.Names}}"',
    'ls /home/ubuntu/gateway-nginx/ 2>/dev/null || echo "not found"',
    'find /home/ubuntu -name "*.conf" -path "*/conf.d/*" 2>/dev/null | head -10',
    'find /home/ubuntu -name "projects" -type d 2>/dev/null | head -5',
]
for cmd in cmds:
    print(f'>>> {cmd}')
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    if out.strip(): print(out.strip())
c.close()
