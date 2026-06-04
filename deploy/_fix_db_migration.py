import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=15)

# Check backend logs for error
cmd = 'docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -30'
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print('BACKEND LOGS:')
print(stdout.read().decode()[-2000:])

ssh.close()
