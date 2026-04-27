"""Upload fixed files and restart backend container."""
import paramiko

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)

sftp = ssh.open_sftp()

files_to_upload = [
    ("backend/app/models/models.py", f"{REMOTE_DIR}/backend/app/models/models.py"),
    ("backend/app/main.py", f"{REMOTE_DIR}/backend/app/main.py"),
]

import os
for local_rel, remote_path in files_to_upload:
    local_path = os.path.join(LOCAL_DIR, local_rel)
    print(f"Uploading {local_rel} ...")
    sftp.put(local_path, remote_path)

sftp.close()
print("Files uploaded.")

print("Rebuilding and restarting backend container...")
cmd = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --build backend 2>&1"
print(f"CMD: {cmd}")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)
exit_code = stdout.channel.recv_exit_status()
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print(f"STDOUT: {out[:3000]}")
if err.strip():
    print(f"STDERR: {err[:1000]}")
print(f"EXIT: {exit_code}")

import time
print("Waiting 20s for backend to start...")
time.sleep(20)

print("\nChecking backend container status...")
stdin, stdout, stderr = ssh.exec_command(
    f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps backend 2>&1", timeout=30
)
print(stdout.read().decode("utf-8", errors="replace"))

print("\nChecking backend logs...")
stdin, stdout, stderr = ssh.exec_command(
    f"docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail=30 2>&1", timeout=30
)
print(stdout.read().decode("utf-8", errors="replace")[:3000])

print("\nVerifying links...")
urls = {
    "H5 Frontend": "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/",
    "Admin Frontend": "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/",
    "API Docs": "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs",
}

for name, url in urls.items():
    stdin, stdout, stderr = ssh.exec_command(
        f"curl -sL -o /dev/null -w '%{{http_code}}' --max-time 30 '{url}'", timeout=60
    )
    status = stdout.read().decode("utf-8", errors="replace").strip().replace("'", "")
    ok = status in ("200", "301", "302", "307")
    print(f"  {'OK' if ok else 'FAIL'} | {name}: {url} -> HTTP {status}")

ssh.close()
print("\nDone.")
