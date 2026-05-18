import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=30)
for cmd in [
    # 看 backend 容器内 /app/uploads 是什么
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/uploads/ 2>/dev/null | head -10',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/uploads/miniprogram/ 2>/dev/null | head -10',
    'docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format "{{json .Mounts}}" 2>/dev/null',
]:
    _, o, _ = c.exec_command(cmd, timeout=20)
    print('---', cmd)
    print(o.read().decode()[:2000])
c.close()
