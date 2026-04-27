import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

cmds = [
    'docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | head -120',
    'docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -iE "error|Error|import|module|ModuleNotFound|No module|Traceback|raise" | head -40',
]

for cmd in cmds:
    print(f'=== {cmd[:80]} ===')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace')
    print(out[:4000])
    print()

ssh.close()
