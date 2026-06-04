import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DIR = "/home/ubuntu/%s" % DEPLOY_ID

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=300):
    print("\n$ " + cmd[:120])
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip()[-1500:])
    if err.strip(): print("[stderr] " + err.strip()[-1500:])
    print("[exit %d]" % code)
    return code, out + err

ok = False
for i in range(5):
    print("=== attempt %d ===" % (i+1))
    code, _ = run("cd %s && git -c http.postBuffer=524288000 fetch origin master --no-tags 2>&1" % DIR, t=300)
    if code == 0:
        ok = True
        break
if ok:
    run("cd %s && git reset --hard origin/master && git log -1 --oneline" % DIR)
else:
    print("\n!!! GIT FETCH STILL FAILING -> will use SFTP fallback")
c.close()
