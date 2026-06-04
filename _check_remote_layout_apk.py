import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads/",
    "docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' | head -40",
    "cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.yml 2>/dev/null | head -100",
]
for c in cmds:
    print(f"\n=== {c} ===", flush=True)
    stdin, stdout, stderr = ssh.exec_command(c)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    print(out)
    if err: print("STDERR:", err)
ssh.close()
