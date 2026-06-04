import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
cmd = f'cd /home/ubuntu/{DEPLOY_ID} && grep -E "^\\s*(services:|h5|admin|backend|container_name|build:|context:|dockerfile:|image:)" docker-compose.yml | head -60'
i,o,e = c.exec_command(cmd, timeout=20)
print(o.read().decode('utf-8', errors='replace'))
c.close()
