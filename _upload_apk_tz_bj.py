import paramiko
import sys
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads"

with open("_apk_name.txt", "r") as f:
    fname = f.read().strip()

local_path = os.path.join("_apk_dl", fname)
remote_path = f"{REMOTE_DIR}/{fname}"

print(f"Uploading {local_path} -> {remote_path}", flush=True)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
stdout.channel.recv_exit_status()

sftp = ssh.open_sftp()
sftp.put(local_path, remote_path)
sftp.chmod(remote_path, 0o644)
attrs = sftp.stat(remote_path)
print(f"Uploaded size: {attrs.st_size}", flush=True)
sftp.close()
ssh.close()
print("OK")
