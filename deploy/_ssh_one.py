import paramiko, sys
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
cmd = sys.argv[1]
_,o,e=c.exec_command(cmd, timeout=120)
print(o.read().decode(errors='ignore'))
err=e.read().decode(errors='ignore')
if err.strip(): print('STDERR:', err)
c.close()
