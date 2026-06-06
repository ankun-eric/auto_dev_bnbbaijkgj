import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

cmds = [
    ('gateway .server文件', 'cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.server 2>/dev/null || echo "NOT FOUND"'),
    ('gateway .conf文件', 'cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>/dev/null || echo "NOT FOUND"'),
    ('gateway主nginx.conf', 'grep -A2 "include.*6b099ed3" /home/ubuntu/gateway/nginx.conf 2>/dev/null'),
    ('当前使用的compose', 'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && ls -la docker-compose*.yml 2>/dev/null'),
    ('docker compose ps', 'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml ps 2>&1 | head -10'),
    ('init.sql存在', 'ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend/init.sql 2>/dev/null || echo "NOT FOUND"'),
]

for name, cmd in cmds:
    print(f'\n=== {name} ===')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(out[:1500] or '(空)')
    if err:
        print(f'[stderr]: {err[:200]}')

client.close()
print('\nDone.')
