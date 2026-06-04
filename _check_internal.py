import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

cmds = [
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 curl -s -o /dev/null -w "in:/h5/ai-home HTTP %{http_code}\\n" http://localhost:3001/h5/ai-home',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 curl -s -o /dev/null -w "in:/h5/login HTTP %{http_code}\\n" http://localhost:3001/h5/login',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 curl -s -o /dev/null -w "in:/h5 HTTP %{http_code}\\n" http://localhost:3001/h5',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 curl -s -o /dev/null -w "in:/ai-home HTTP %{http_code}\\n" http://localhost:3001/ai-home',
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode().strip())
c.close()
