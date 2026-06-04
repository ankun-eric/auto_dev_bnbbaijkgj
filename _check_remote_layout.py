import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
cmd = f'ls /home/ubuntu/{DEPLOY_ID}/ | head -40 && echo "---compose---" && ls /home/ubuntu/{DEPLOY_ID}/docker-compose* 2>/dev/null && echo "---containers---" && docker ps --format "{{{{.Names}}}}\\t{{{{.Status}}}}" | grep {DEPLOY_ID}'
i,o,e = c.exec_command(cmd, timeout=30)
print(o.read().decode('utf-8', errors='replace'))
c.close()
