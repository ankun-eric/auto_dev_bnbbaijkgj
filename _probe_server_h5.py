import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
cmds = [
    'whoami',
    'sudo -n docker ps --format "{{.Names}}" | head -40',
    f'sudo -n docker ps --format "{{{{.Names}}}}" | grep -i h5-web',
    f'ls -la /home/ubuntu/{PROJECT_ID}/ 2>&1 | head -20',
    f'ls -la /home/ubuntu/{PROJECT_ID}/h5-web/public/ 2>&1 | head -10',
]
for cmd in cmds:
    print('==>', cmd)
    i, o, e = c.exec_command(cmd, timeout=30)
    print('OUT:', o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err:
        print('ERR:', err)
c.close()
