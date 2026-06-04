import paramiko
import os

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj\deploy"

def run_ssh(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

files = {
    "docker-compose.prod.yml": f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml",
    "gateway-routes.conf": f"/home/ubuntu/{DEPLOY_ID}/gateway-routes.conf",
    ".env": f"/home/ubuntu/{DEPLOY_ID}/.env",
}

for local_name, remote_path in files.items():
    local_path = os.path.join(LOCAL_DIR, local_name)
    print(f"Reading: {remote_path}")
    out, err, code = run_ssh(client, f"cat {remote_path} 2>/dev/null || echo 'FILE_NOT_FOUND'")
    if "FILE_NOT_FOUND" in out:
        print(f"  File not found: {remote_path}")
        continue
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Saved to {local_path} ({len(out)} bytes)")

# Check for .env.production
print("\nChecking .env.production...")
out, err, code = run_ssh(client, f"cat /home/ubuntu/{DEPLOY_ID}/.env.production 2>/dev/null || echo 'FILE_NOT_FOUND'")
if "FILE_NOT_FOUND" not in out:
    local_path = os.path.join(LOCAL_DIR, ".env.production")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Saved .env.production ({len(out)} bytes)")
else:
    print("  .env.production not found")

# Check flutter_app for APP detection
print("\n=== APP 端检测 ===")
out, err, code = run_ssh(client, f"ls -la /home/ubuntu/{DEPLOY_ID}/flutter_app/ 2>/dev/null | head -20 || echo 'NO_APP'")
if "NO_APP" in out:
    print("  项目不包含 APP 端")
else:
    print("  项目包含 flutter_app 目录")
    print(out[:1000])

client.close()
print("\nAll configs fetched.")
