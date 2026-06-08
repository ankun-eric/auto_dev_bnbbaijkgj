import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

stdin, stdout, stderr = ssh.exec_command('cat /home/ubuntu/gateway/nginx.conf', timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("=== nginx.conf ===")
print(out)
if err:
    print("STDERR:", err)

stdin2, stdout2, stderr2 = ssh.exec_command('ls -la /home/ubuntu/gateway/conf.d/6b099ed3* 2>&1', timeout=15)
out2 = stdout2.read().decode('utf-8', errors='replace')
err2 = stderr2.read().decode('utf-8', errors='replace')
print("\n=== conf.d files ===")
print(out2)
if err2:
    print("STDERR:", err2)

stdin3, stdout3, stderr3 = ssh.exec_command('cat /home/ubuntu/gateway/conf.d/6b099ed3* 2>&1', timeout=15)
out3 = stdout3.read().decode('utf-8', errors='replace')
err3 = stderr3.read().decode('utf-8', errors='replace')
print("\n=== conf.d content ===")
print(out3)
if err3:
    print("STDERR:", err3)

ssh.close()
print("\nDONE")
