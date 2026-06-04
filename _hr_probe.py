import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=60):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return out, err

cmds = [
    "ls -d /home/ubuntu/%s 2>/dev/null && echo DIR_OK" % DEPLOY_ID,
    "docker ps --format '{{.Names}}' | grep -iE 'gateway|nginx'",
    "docker ps --format '{{.Names}}' | grep %s" % DEPLOY_ID,
    "cd /home/ubuntu/%s && git log -1 --oneline 2>&1" % DEPLOY_ID,
    "cd /home/ubuntu/%s && git remote -v 2>&1 | head -2" % DEPLOY_ID,
]
for cmd in cmds:
    out, err = run(cmd)
    print("### " + cmd)
    print((out or err).strip())
    print()

c.close()
