import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=15)

cmds = [
    'ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/ 2>&1 | head -n 20',
    'docker ps --format "{{.Names}}" | grep -i 6b099ed3 || true',
    'docker ps --format "{{.Names}}" | grep -i gateway || true',
    'docker inspect gateway --format "{{json .Mounts}}" 2>&1 | head -c 2000',
    'sudo -n ls -la /etc/nginx/conf.d/ 2>&1 | head -n 5 || ls -la /etc/nginx/conf.d/ 2>&1 | head -n 5 || true',
    'find /home/ubuntu /data /srv /opt -maxdepth 6 -name "6b099ed3-7175-4a78-91f4-44570c84ed27.conf" -type f 2>/dev/null | head',
]
for cmd in cmds:
    print('$', cmd)
    i, o, e = c.exec_command(cmd)
    out = o.read().decode('utf-8', 'ignore')
    err = e.read().decode('utf-8', 'ignore')
    print(out)
    if err.strip():
        print('STDERR:', err)
    print('---')
c.close()
