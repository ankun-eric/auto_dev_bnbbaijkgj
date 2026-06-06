import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

cmds = [
    ('DB容器', 'docker ps -a --filter name=6b099ed3-db --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'),
    ('项目目录', 'ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>/dev/null | head -20'),
    ('当前compose', 'head -40 /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.yml 2>/dev/null || echo "no docker-compose.yml"'),
    ('prod compose', 'head -40 /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.prod.yml 2>/dev/null || echo "no docker-compose.prod.yml"'),
    ('git log', 'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git log --oneline -3 2>/dev/null || echo "not a git repo"'),
    ('gateway配置', 'head -30 /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>/dev/null || echo "no gateway config"'),
]

for name, cmd in cmds:
    print(f'\n=== {name} ===')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(out[:800] or '(空)')
    if err:
        print(f'[stderr]: {err[:200]}')

client.close()
print('\nDone.')
