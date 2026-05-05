import paramiko

SERVER = "newbb.test.bangbangvip.com"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ | head -50",
    "docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' | grep -iE '6b099|gateway|nginx'",
    "docker ps --format '{{.Names}}' | head -40",
    # find recent apk/zip files served via the URL
    "find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 -maxdepth 3 -name '*.apk' -o -name '*.zip' 2>/dev/null | head -20",
    "cat /etc/nginx/conf.d/*.conf 2>/dev/null | grep -A3 -B1 6b099 | head -80",
    "docker inspect $(docker ps --format '{{.Names}}' | grep -i gateway | head -1) 2>/dev/null | grep -A2 -i 'mount\\|source\\|destination' | head -60",
]

for c in cmds:
    print("=" * 80)
    print("$ " + c)
    stdin, stdout, stderr = ssh.exec_command(c, timeout=30)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out:
        print(out)
    if err:
        print("STDERR:", err)

ssh.close()
