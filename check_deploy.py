#!/usr/bin/env python3
"""快速部署检查"""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)

cmds = [
    'grep -c "随便选" /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/src/app/brain-game/page.tsx 2>/dev/null || echo "NOT_FOUND"',
    'test -f /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/public/brain-game.html && echo "EXISTS" || echo "NOT_FOUND"',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-frontend test -f /app/public/brain-game.html && echo "DOCKER_EXISTS" || echo "DOCKER_NOT_FOUND"',
]

for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f'CMD: {cmd[:60]}...')
    print(f'  OUT: {out[:200]}')
    if err:
        print(f'  ERR: {err[:200]}')

ssh.close()
