import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=30)
for cmd in [
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads/miniprogram/ | head -5',
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads/ 2>/dev/null',
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ | head -25',
    'docker ps --filter name=6b099ed3 --format "{{.Names}}"',
    'cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/nginx*.conf 2>/dev/null | head -80',
    'find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 -name "miniprogram_20260517_144324*" 2>/dev/null',
]:
    _, o, _ = c.exec_command(cmd, timeout=20)
    print('---', cmd)
    print(o.read().decode())
c.close()
