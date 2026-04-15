import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888')

commands = [
    'docker inspect gateway-nginx --format "{{json .Mounts}}" 2>/dev/null | python3 -m json.tool',
    'ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/ 2>/dev/null',
    'cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.prod.yml 2>/dev/null | grep -A5 -B5 static',
]

for cmd in commands:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

ssh.close()
