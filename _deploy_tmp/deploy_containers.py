import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888')

commands = [
    'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d 2>&1',
    'sleep 10 && docker ps --filter name=6b099ed3 --format "table {{.Names}}\t{{.Status}}"',
    'docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>&1 || echo already connected',
]
for cmd in commands:
    print(f'>>> {cmd[:80]}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out)
    if err: print(err[-300:])
    print(f'Exit: {stdout.channel.recv_exit_status()}')
    print('---')
ssh.close()
