import paramiko
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

with open("_apk_name.txt", "r") as f:
    fname = f.read().strip()

local_path = os.path.join("_apk_dl", fname)
remote_tmp = f"/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads/{fname}"

print(f"Local: {local_path}")
print(f"Remote tmp (host): {remote_tmp}")
print(f"Target container path: {CONTAINER}:/app/uploads/{fname}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

# Already uploaded to host path, just docker cp into container
cmd = f"docker cp {remote_tmp} {CONTAINER}:/app/uploads/{fname} && docker exec {CONTAINER} chmod 644 /app/uploads/{fname} && docker exec {CONTAINER} ls -la /app/uploads/{fname}"
print(f"\n=== {cmd} ===", flush=True)
stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode(errors='replace')
err = stderr.read().decode(errors='replace')
print(out)
if err: print("STDERR:", err)
ssh.close()
print("Done")
