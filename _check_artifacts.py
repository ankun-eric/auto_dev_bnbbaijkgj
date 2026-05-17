import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=20)

cmds = [
    "ls -la /home/ubuntu/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>/dev/null | head -30",
    "find /home/ubuntu/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27 -maxdepth 4 -name '*.zip' 2>/dev/null",
    "find /var/www -maxdepth 6 -name '*.zip' 2>/dev/null | grep 6b099 | head -10",
    "ls /home/ubuntu/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/public/static/ 2>/dev/null",
]
for cmd in cmds:
    print(f"=== $ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err.strip():
        print("ERR:", err)
c.close()
