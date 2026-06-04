import paramiko, sys
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "docker ps --filter name=6b099ed3 --format '{{.Names}}\\t{{.Image}}\\t{{.Status}}'",
    "H=$(docker ps -qf 'name=6b099ed3.*h5'); docker exec $H ls -la /app",
    "H=$(docker ps -qf 'name=6b099ed3.*h5'); docker exec $H ls /app/.next 2>&1 | head -5 || true",
    "H=$(docker ps -qf 'name=6b099ed3.*h5'); docker exec $H sh -c 'cat /app/package.json | head -30'",
]
for c in cmds:
    print(f"\n>>> {c[:100]}")
    stdin, stdout, stderr = cli.exec_command(c, timeout=30)
    print(stdout.read().decode('utf-8', errors='replace'))
    e = stderr.read().decode('utf-8', errors='replace')
    if e.strip():
        print("STDERR:", e)
cli.close()
