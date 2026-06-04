import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

container = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

cmds = [
    f"docker exec {container} ls -la /app/uploads/ 2>&1 | head -40",
    f"docker exec {container} sh -c 'ls -la /app/uploads/*.apk 2>&1 || echo no-apk'",
    # check nginx route for /uploads/
    "ls /home/ubuntu/gateway-nginx/conf.d/ 2>/dev/null || ls /home/ubuntu/nginx-gateway/ 2>/dev/null",
    "docker ps --filter name=gateway --format '{{.Names}}'",
    "docker ps --filter name=nginx --format '{{.Names}}'",
]
for c in cmds:
    print(f"\n=== {c} ===", flush=True)
    stdin, stdout, stderr = ssh.exec_command(c)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    print(out)
    if err: print("STDERR:", err)
ssh.close()
