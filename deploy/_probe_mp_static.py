import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=20)

cmds = [
    "cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf",
    "docker inspect gateway --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}\\n{{end}}'",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/",
    "ls /data/static/downloads/ 2>/dev/null || echo NO_DATA_STATIC_DOWNLOADS_HOST",
    "docker exec gateway ls /data/static/downloads/ 2>/dev/null || echo NO_GATEWAY_PATH",
]
for cmd in cmds:
    print('===', cmd)
    i, o, e = c.exec_command(cmd)
    print(o.read().decode('utf-8', 'ignore'))
    err = e.read().decode('utf-8', 'ignore')
    if err.strip():
        print('STDERR:', err)
c.close()
