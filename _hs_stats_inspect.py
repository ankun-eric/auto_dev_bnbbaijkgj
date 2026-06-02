import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=120):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

cmds = [
    f"ls -la /home/ubuntu/{DID}/ 2>&1 | head -40",
    f"cd /home/ubuntu/{DID} && git log -1 --oneline 2>&1",
    f"ls /home/ubuntu/{DID}/*.yml /home/ubuntu/{DID}/docker-compose* 2>&1",
    "docker ps --format '{{.Names}}' | grep -iE 'gateway|nginx' 2>&1",
    f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DID} 2>&1",
    "ls /home/ubuntu/gateway/conf.d/ 2>&1 | head",
]
for cmd in cmds:
    o, e = run(cmd)
    print(f"\n$ {cmd}\n{o}{e}")

c.close()
