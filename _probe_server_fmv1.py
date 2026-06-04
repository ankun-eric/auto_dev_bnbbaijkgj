import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cmds = [
    "ls -d /home/ubuntu/%s 2>/dev/null && echo '---'" % DEPLOY_ID,
    "ls /home/ubuntu/%s 2>/dev/null | head -50" % DEPLOY_ID,
    "docker ps --format '{{.Names}}' | grep %s" % DEPLOY_ID,
    "docker ps --format '{{.Names}}' | grep -i gateway",
    "ls /home/ubuntu/%s/h5-web 2>/dev/null | head" % DEPLOY_ID,
    "cat /home/ubuntu/%s/docker-compose.prod.yml 2>/dev/null | head -120" % DEPLOY_ID,
    "cd /home/ubuntu/%s && git log -1 --oneline 2>/dev/null" % DEPLOY_ID,
    "cd /home/ubuntu/%s && git remote -v 2>/dev/null" % DEPLOY_ID,
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)
for cmd in cmds:
    print("\n$ " + cmd)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    print(out)
    if err.strip():
        print("[stderr]", err)
c.close()
