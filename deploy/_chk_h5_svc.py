import paramiko
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
for cmd in [
    'grep -nE "^  [a-z0-9_-]+:" /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.yml',
    'sed -n "/h5/,/networks:/p" /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.yml | head -40',
]:
    print('>>>', cmd)
    i, o, e = s.exec_command(cmd)
    print(o.read().decode('utf-8', 'replace'))
s.close()
