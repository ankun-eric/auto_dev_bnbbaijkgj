import paramiko
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
cmd = (
    'ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/ 2>&1 | head -20'
)
i, o, e = s.exec_command(cmd)
print(o.read().decode())
print('ERR:', e.read().decode())
s.close()
