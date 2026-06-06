import paramiko, traceback

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

with open(r'C:\auto_output\bnbbaijkgj\_system_py_check.txt', 'w') as f:
    try:
        # Check system.py in container
        stdin, stdout, stderr = ssh.exec_command('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend cat /app/app/api/system.py 2>&1')
        code = stdout.read().decode() + stderr.read().decode()
        f.write("=== Container system.py (lines 30-50) ===\n")
        lines = code.split('\n')
        for i in range(30, min(50, len(lines))):
            f.write(f"L{i+1}: {lines[i]}\n")

        # Also check git log on server
        stdin, stdout, stderr = ssh.exec_command('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git log -1 --oneline && echo --- && git show --stat HEAD 2>&1 | head -10')
        f.write("\n=== Server Git ===\n")
        f.write(stdout.read().decode())

        # Check docker image info
        stdin, stdout, stderr = ssh.exec_command('docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format "{{.Created}} {{.Id}}"')
        f.write("\n=== Backend image ===\n")
        f.write(stdout.read().decode())

    except Exception as e:
        f.write(f'ERROR: {e}\n{traceback.format_exc()}\n')

ssh.close()
print('Done')
