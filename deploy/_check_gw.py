import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)
cmds = [
    "docker inspect gateway --format '{{json .Mounts}}'",
    "ls /data/static/ 2>&1",
    "ls /data/static/miniprogram/ 2>&1 | head -20",
]
for c in cmds:
    print(f">>> {c}")
    i, o, e = ssh.exec_command(c)
    print(o.read().decode("utf-8", errors="replace"))
ssh.close()
