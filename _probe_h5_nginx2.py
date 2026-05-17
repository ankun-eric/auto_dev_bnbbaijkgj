import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
PID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
cmds = [
    f'sudo -n docker exec gateway cat /etc/nginx/conf.d/{PID}.conf',
    'sudo -n docker inspect gateway --format "{{json .Mounts}}"',
]
for cmd in cmds:
    print('==>', cmd)
    i, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err:
        print('ERR:', err)
    print()
c.close()
