import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "docker exec gateway ls /etc/nginx/conf.d/",
    "docker exec gateway cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>/dev/null | head -5 || echo NO_CONF_FOUND",
    "docker inspect gateway --format='{{range .Mounts}}{{.Source}}:{{.Destination}}:RW={{.RW}} {{end}}'",
]

for cmd in cmds:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    ec = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"STDERR: {err.strip()}")
    print(f"Exit: {ec}")

ssh.close()
