import paramiko
import os

HOST = "newbb.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

sftp = client.open_sftp()
local_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_package.tar.gz")
sftp.put(local_file, f"{REMOTE_DIR}/deploy_package.tar.gz")
sftp.close()
print("Uploaded hotfix package")

cmds = [
    f"cd {REMOTE_DIR} && tar xzf deploy_package.tar.gz",
    f"cd {REMOTE_DIR} && docker compose restart backend",
]
for cmd in cmds:
    print(f"\n>>> {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip())
    if err.strip(): print(f"[STDERR] {err.strip()}")
    print(f"[EXIT] {code}")

import time
print("\nWaiting 15s for backend to restart...")
time.sleep(15)

_, stdout, stderr = client.exec_command(
    f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com/autodev/{DEPLOY_ID}/api/health",
    timeout=30
)
print(f"Health check: {stdout.read().decode().strip()}")
client.close()
print("Hotfix deployed!")
