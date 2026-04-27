import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "docker exec gateway cat /etc/nginx/nginx.conf 2>/dev/null | head -100",
    "docker exec gateway ls /etc/nginx/conf.d/ 2>/dev/null",
    "docker exec gateway cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -200",
    "docker exec gateway find /etc/nginx -name '*.conf' 2>/dev/null",
    "docker inspect gateway --format='{{json .Mounts}}' 2>/dev/null",
    "curl -sI https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/nginx.conf 2>/dev/null",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/nginx.conf",
    "cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/nginx.conf",
]

for cmd in cmds:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
