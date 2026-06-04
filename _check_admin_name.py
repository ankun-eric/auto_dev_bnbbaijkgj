import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
_,o,_=c.exec_command('docker ps --format "{{.Names}}" | grep 6b099ed3')
print(o.read().decode())
c.close()
