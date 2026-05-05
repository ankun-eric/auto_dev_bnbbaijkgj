import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=60)
_, o, e = c.exec_command('find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ -name "*.apk" 2>/dev/null | head -20', timeout=60)
print(o.read().decode())
print('ERR:', e.read().decode())
c.close()
