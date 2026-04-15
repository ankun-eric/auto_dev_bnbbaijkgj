import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=30)

commands = [
    f"docker exec gateway cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -A10 '{DEPLOY_ID}'",
    f"docker exec gateway ls /etc/nginx/conf.d/ 2>/dev/null",
    f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf 2>/dev/null || echo 'no separate conf'",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>/dev/null",
    f"docker exec {DEPLOY_ID}-backend ls /app/ 2>/dev/null | head -20",
    f"docker exec {DEPLOY_ID}-backend ls /app/uploads/ 2>/dev/null || echo 'no uploads dir'",
    f"docker exec {DEPLOY_ID}-admin ls /usr/share/nginx/html/ 2>/dev/null | head -10",
    f"docker exec {DEPLOY_ID}-h5 ls /usr/share/nginx/html/ 2>/dev/null | head -10",
    f"docker volume inspect {DEPLOY_ID}_uploads_data 2>/dev/null | head -20",
]

for cmd in commands:
    print(f"\n=== {cmd[:80]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err: print(f"ERR: {err}")

ssh.close()
