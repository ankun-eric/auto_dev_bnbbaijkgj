# -*- coding: utf-8 -*-
"""Quick checks on server state for h5 container + nginx routing."""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username="ubuntu", password="Newbang888", timeout=30)

def run(cmd):
    print(f"\n$ {cmd}")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120, get_pty=True)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    print(out)
    if err:
        print("STDERR:", err)
    return stdout.channel.recv_exit_status(), out

run("docker ps --format '{{.Names}}' | grep " + DEPLOY_ID)
run(f"docker exec {DEPLOY_ID}-h5 ls /app/.next/server/app/points 2>/dev/null | head -20")
run(f"docker exec {DEPLOY_ID}-h5 cat /etc/hostname")
# nginx
run(f"docker ps --format '{{{{.Names}}}}' | grep -i gateway")
run(f"curl -s -o /dev/null -w 'no-redir %{{http_code}} | followed %{{redirect_url}}\\n' http://localhost/autodev/{DEPLOY_ID}/points")
run(f"curl -s -o /dev/null -w '%{{http_code}}\\n' -L http://localhost/autodev/{DEPLOY_ID}/points/")
run(f"curl -sI http://localhost/autodev/{DEPLOY_ID}/points 2>&1 | head -10")
run(f"curl -sI http://localhost/autodev/{DEPLOY_ID}/points/ 2>&1 | head -10")

ssh.close()
