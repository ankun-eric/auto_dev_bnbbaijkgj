"""仅部署 backend"""
import time, paramiko
from pathlib import Path

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_DIR = f"/home/ubuntu/{PROJECT_ID}"

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

def run(c, timeout=600):
    print("$", c)
    si,so,se = cli.exec_command(c, timeout=timeout)
    out = so.read().decode("utf-8","ignore") + se.read().decode("utf-8","ignore")
    rc = so.channel.recv_exit_status()
    print(out[-2000:])
    return rc

sftp = cli.open_sftp()
local = "backend/app/api/questionnaire.py"
remote = f"{DEPLOY_DIR}/backend/app/api/questionnaire.py"
sftp.put(local, remote)
print(f"uploaded {local}")
sftp.close()

run(f"cd {DEPLOY_DIR} && docker compose build backend 2>&1 | tail -50", 1800)
run(f"cd {DEPLOY_DIR} && docker compose up -d backend 2>&1 | tail -20", 300)
time.sleep(20)
run(f"curl -sk -o /dev/null -w 'HTTP_%{{http_code}}\\n' 'https://{HOST}/autodev/{PROJECT_ID}/api/health'", 60)
cli.close()
print("DONE")
