import paramiko
HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

cmds = [
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/',
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads/ 2>&1 | head -30',
    'find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 -maxdepth 4 -name "miniprogram_*.zip" 2>/dev/null | head -20',
    'docker ps --format "{{.Names}}\t{{.Image}}\t{{.Ports}}" | head -30',
]
for c in cmds:
    print('>>>', c)
    stdin, stdout, stderr = cli.exec_command(c)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err: print('ERR:', err)
cli.close()
