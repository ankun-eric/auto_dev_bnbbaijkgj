import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DIR = "/home/ubuntu/%s" % DEPLOY_ID

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=600):
    print("\n$ " + cmd)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip()[-3000:])
    if err.strip(): print("[stderr] " + err.strip()[-2000:])
    print("[exit %d]" % code)
    return code

run("cd %s && git fetch origin master --no-tags 2>&1" % DIR, t=300)
run("cd %s && git reset --hard origin/master && git log -1 --oneline" % DIR)
run("cd %s && git log --oneline -3 -- h5-web/src/app/health-metric/'[type]'/page.tsx" % DIR)
c.close()
