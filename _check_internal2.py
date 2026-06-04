import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

# 从 backend 容器调用 h5 容器
cmds = [
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w "/h5/ai-home HTTP %{http_code}\\n" http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3001/h5/ai-home',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w "/h5/login HTTP %{http_code}\\n" http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3001/h5/login',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w "/h5/ HTTP %{http_code}\\n" http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3001/h5/',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w "/ai-home HTTP %{http_code}\\n" http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3001/ai-home',
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    rc = o.channel.recv_exit_status()
    so = o.read().decode().strip()
    se = e.read().decode().strip()
    print(so or se)
c.close()
