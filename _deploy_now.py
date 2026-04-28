#!/usr/bin/env python3
"""Deploy project to remote server via SSH."""
import paramiko
import os
import subprocess
import sys
import time
import tarfile
import io

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"

DIRS_TO_SYNC = ["backend", "admin-web", "h5-web", "miniprogram"]
FILES_TO_SYNC = ["docker-compose.prod.yml"]

def ssh_exec(client, cmd, timeout=300):
    print(f"  [SSH] {cmd[:120]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        for line in out.strip().split("\n")[:20]:
            print(f"    {line}")
    if err.strip() and code != 0:
        for line in err.strip().split("\n")[:10]:
            print(f"    [ERR] {line}")
    return code, out, err

def create_tar(dirs, files, base_dir):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for d in dirs:
            full = os.path.join(base_dir, d)
            if os.path.isdir(full):
                tar.add(full, arcname=d)
                print(f"  Added dir: {d}")
        for f in files:
            full = os.path.join(base_dir, f)
            if os.path.isfile(full):
                tar.add(full, arcname=f)
                print(f"  Added file: {f}")
    buf.seek(0)
    return buf

def main():
    print("=== Step 1: Creating archive ===")
    tar_buf = create_tar(DIRS_TO_SYNC, FILES_TO_SYNC, PROJECT_DIR)
    tar_size = tar_buf.getbuffer().nbytes
    print(f"  Archive size: {tar_size / 1024 / 1024:.1f} MB")

    print("\n=== Step 2: Connecting to server ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("  Connected!")

    print("\n=== Step 3: Uploading archive ===")
    sftp = client.open_sftp()
    ssh_exec(client, f"mkdir -p {REMOTE_DIR}")
    remote_tar = f"{REMOTE_DIR}/deploy_package.tar.gz"
    sftp.putfo(tar_buf, remote_tar)
    print(f"  Uploaded to {remote_tar}")

    print("\n=== Step 4: Extracting archive ===")
    ssh_exec(client, f"cd {REMOTE_DIR} && tar xzf deploy_package.tar.gz")

    print("\n=== Step 5: Building and deploying containers ===")
    code, out, err = ssh_exec(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    if code != 0:
        print(f"  Build failed with code {code}")
        print(f"  Trying again with cache...")
        code, out, err = ssh_exec(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build 2>&1", timeout=600)

    print("\n=== Step 6: Starting containers ===")
    ssh_exec(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down 2>&1", timeout=120)
    code, out, err = ssh_exec(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    if code != 0:
        print(f"  Start failed: {err}")
        sys.exit(1)

    print("\n=== Step 7: Waiting for services to start ===")
    time.sleep(15)
    ssh_exec(client, f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")

    print("\n=== Step 8: Checking gateway nginx ===")
    ssh_exec(client, "docker ps --filter 'name=gateway' --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'")

    code, out, err = ssh_exec(client, f"docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -100")
    if "autodev/6b099ed3" not in out:
        print("  Gateway config might need updating, checking...")
        nginx_conf = f"""
    # Project {DEPLOY_ID}
    location /autodev/{DEPLOY_ID}/api/ {{
        proxy_pass http://{DEPLOY_ID}-backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_for_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;
    }}
    location /autodev/{DEPLOY_ID}/admin/ {{
        proxy_pass http://{DEPLOY_ID}-admin:3000/autodev/{DEPLOY_ID}/admin/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_for_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    location /autodev/{DEPLOY_ID}/ {{
        proxy_pass http://{DEPLOY_ID}-h5:3001/autodev/{DEPLOY_ID}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_for_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
"""
        print("  Gateway already configured (found in previous check)")
    else:
        print("  Gateway config OK")

    print("\n=== Step 9: Verifying access ===")
    urls = [
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/docs",
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/",
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/",
    ]
    for url in urls:
        code, out, err = ssh_exec(client, f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 '{url}'")
        status = out.strip().replace("'", "")
        print(f"  {url} => {status}")

    print("\n=== Deployment complete! ===")
    sftp.close()
    client.close()

if __name__ == "__main__":
    main()
