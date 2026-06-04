import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(cli, cmd, timeout=120):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

cmds = [
    f"ls -d /home/{USER}/{DEPLOY_ID} 2>/dev/null && echo PROJ_OK",
    f"ls /home/{USER}/{DEPLOY_ID} 2>/dev/null",
    f"cat /home/{USER}/{DEPLOY_ID}/docker-compose*.yml 2>/dev/null | head -80",
    "docker ps --format '{{.Names}}' | grep " + DEPLOY_ID,
]
for c in cmds:
    print("### CMD:", c)
    out, err = run(cli, c)
    print(out)
    if err.strip():
        print("ERR:", err)
    print("=" * 60)
cli.close()
