import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30, look_for_keys=False, allow_agent=False)
for cmd in [
    "docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format '{{json .Mounts}}'",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/app/api/glucose_v1.py",
    "ls /home/ubuntu/ | head",
    "find / -type d -name 'autodev' 2>/dev/null | head -5",
    "find /home /opt /srv -name 'docker-compose*' 2>/dev/null | grep -i 6b099ed3 | head -5",
    "find / -type d -name '*6b099ed3*' 2>/dev/null | head -10",
]:
    print('$', cmd)
    si, so, se = c.exec_command(cmd, timeout=60)
    o = so.read().decode('utf-8', errors='ignore')
    print(o[:1500])
    e = se.read().decode('utf-8', errors='ignore')
    if e:
        print('ERR:', e[:200])
    print('---')
