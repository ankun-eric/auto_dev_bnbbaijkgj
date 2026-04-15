import paramiko
import sys
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ZIP_NAME = "miniprogram_20260415_214229_fmkv.zip"
LOCAL_ZIP = os.path.join(r"C:\auto_output\bnbbaijkgj", ZIP_NAME)
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/"
REMOTE_ZIP = f"{REMOTE_DIR}{ZIP_NAME}"
CONTAINER_BACKEND = f"{DEPLOY_ID}-backend"

def ssh_exec(ssh, cmd):
    print(f"[SSH] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    return out.strip(), err.strip(), exit_code

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=15)
    print("Connected.")

    # Step 1: Check nginx gateway config
    print("\n=== Checking gateway nginx config ===")
    out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-gateway cat /etc/nginx/conf.d/default.conf 2>/dev/null || echo 'NO_CONF'")
    nginx_conf = out

    # Step 2: Check if backend has uploads directory and static file serving
    print("\n=== Checking backend uploads directory ===")
    ssh_exec(ssh, f"docker exec {CONTAINER_BACKEND} ls -la /app/uploads/ 2>/dev/null || echo 'NO_UPLOADS_DIR'")

    # Step 3: Check backend static file route config
    print("\n=== Checking if backend serves /uploads/ ===")
    ssh_exec(ssh, f"docker exec {CONTAINER_BACKEND} find /app -name 'main.py' -o -name 'app.py' | head -5")

    # Step 4: Upload zip to server
    print(f"\n=== Uploading {ZIP_NAME} to server ===")
    ssh_exec(ssh, f"mkdir -p {REMOTE_DIR}")
    sftp = ssh.open_sftp()
    sftp.put(LOCAL_ZIP, REMOTE_ZIP)
    sftp.close()
    print(f"Uploaded to {REMOTE_ZIP}")

    # Step 5: Copy zip into backend container uploads
    print("\n=== Copying zip into backend container ===")
    ssh_exec(ssh, f"docker exec {CONTAINER_BACKEND} mkdir -p /app/uploads")
    out, err, code = ssh_exec(ssh, f"docker cp {REMOTE_ZIP} {CONTAINER_BACKEND}:/app/uploads/{ZIP_NAME}")
    if code != 0:
        print(f"docker cp failed with code {code}, trying alternative...")
        ssh_exec(ssh, f"docker cp {REMOTE_ZIP} {CONTAINER_BACKEND}:/app/{ZIP_NAME}")

    # Step 6: Verify file in container
    print("\n=== Verifying file in container ===")
    ssh_exec(ssh, f"docker exec {CONTAINER_BACKEND} ls -la /app/uploads/{ZIP_NAME}")

    # Step 7: Check if there's a static file mount or route for /uploads/
    print("\n=== Checking static files config in nginx ===")
    if "uploads" in nginx_conf.lower() or "static" in nginx_conf.lower():
        print("Gateway has static/uploads route configured.")
    else:
        print("No uploads route found in gateway. Checking backend routes...")
        ssh_exec(ssh, f"docker exec {CONTAINER_BACKEND} grep -r 'uploads' /app/app/ --include='*.py' -l 2>/dev/null | head -5")
        ssh_exec(ssh, f"docker exec {CONTAINER_BACKEND} grep -r 'StaticFiles\\|mount\\|static' /app/app/ --include='*.py' 2>/dev/null | head -10")

    ssh.close()
    print(f"\nDone. Expected URL:")
    print(f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/uploads/{ZIP_NAME}")

if __name__ == "__main__":
    main()
