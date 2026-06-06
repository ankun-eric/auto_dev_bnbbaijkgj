import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

cmds = [
    ('容器详情', 'docker ps -a --filter name=6b099ed3 --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"'),
    ('backend DB_URL', 'docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format "{{.Config.Env}}" 2>/dev/null | tr " " "\\n" | grep DATABASE_URL || echo "no DATABASE_URL"'),
    ('db容器是否存在', 'docker ps -a --filter name=6b099ed3-db --format "{{.Names}} {{.Status}}"'),
    ('网络中的容器', 'docker network inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-network --format "{{range .Containers}}{{.Name}} {{end}}" 2>/dev/null'),
    ('gateway nginx include', 'grep -r "6b099ed3" /home/ubuntu/gateway/ 2>/dev/null | head -5 || echo "no reference in gateway"'),
    ('gateway主配置include', 'grep "include" /home/ubuntu/gateway/nginx.conf 2>/dev/null | head -10 || echo "no nginx.conf"'),
    ('运行的compose', 'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && cat .env 2>/dev/null | head -20 || echo "no .env"'),
    ('所有6b099容器', 'docker ps -a --filter name=6b099ed3 --format "{{.Names}}"'),
    ('gateway容器logs', 'docker logs gateway-nginx --tail 5 2>&1 | head -20'),
]

for name, cmd in cmds:
    print(f'\n=== {name} ===')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(out[:1000] or '(空)')
    if err:
        print(f'[stderr]: {err[:200]}')

client.close()
print('\nDone.')
