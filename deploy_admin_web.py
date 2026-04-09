#!/usr/bin/env python3
"""Deploy admin-web container to remote server."""
import paramiko
import os
import tarfile
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
SERVER_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ADMIN_WEB = r"C:\auto_output\bnbbaijkgj\admin-web"
TAR_NAME = "admin_web_deploy.tar.gz"
LOCAL_TAR = rf"C:\auto_output\bnbbaijkgj\{TAR_NAME}"


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def run_cmd(client, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    return out, err


def pack_admin_web():
    print(f"\n=== Packing admin-web ===")
    excludes = {'node_modules', '.next', '.git', '__pycache__', '.env.local'}
    
    with tarfile.open(LOCAL_TAR, 'w:gz') as tar:
        for root, dirs, files in os.walk(LOCAL_ADMIN_WEB):
            # Filter excluded directories
            dirs[:] = [d for d in dirs if d not in excludes]
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, os.path.dirname(LOCAL_ADMIN_WEB))
                tar.add(filepath, arcname=arcname)
    
    size = os.path.getsize(LOCAL_TAR)
    print(f"Created {LOCAL_TAR} ({size/1024/1024:.1f} MB)")
    return LOCAL_TAR


def upload_file(client, local_path, remote_path):
    print(f"\n=== Uploading {os.path.basename(local_path)} to {remote_path} ===")
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("Upload complete.")


def main():
    # Step 1: Pack admin-web
    pack_admin_web()
    
    # Step 2: Connect to server
    print(f"\n=== Connecting to {HOST} ===")
    client = ssh_connect()
    print("Connected!")
    
    # Step 3: Check current container status
    print("\n=== Step 1: Check container status ===")
    run_cmd(client, f"docker ps | grep {DEPLOY_ID[:8]}")
    
    # Step 4: Upload tar
    print("\n=== Step 2: Upload admin-web ===")
    remote_tar = f"{SERVER_DIR}/{TAR_NAME}"
    upload_file(client, LOCAL_TAR, remote_tar)
    
    # Step 5: Extract and replace admin-web
    print("\n=== Step 3: Extract admin-web on server ===")
    run_cmd(client, f"cd {SERVER_DIR} && tar -xzf {TAR_NAME} && rm {TAR_NAME}")
    run_cmd(client, f"ls {SERVER_DIR}/admin-web/")
    
    # Step 6: Check docker-compose file
    print("\n=== Step 4: Check docker-compose.prod.yml ===")
    out, _ = run_cmd(client, f"cat {SERVER_DIR}/docker-compose.prod.yml")
    
    # Step 7: Rebuild and restart admin-web
    print("\n=== Step 5: Rebuild admin-web container ===")
    run_cmd(client, 
            f"cd {SERVER_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web",
            timeout=600)
    
    print("\n=== Step 6: Start admin-web container ===")
    run_cmd(client, 
            f"cd {SERVER_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web",
            timeout=120)
    
    # Step 8: Verify
    print("\n=== Step 7: Verify container status ===")
    time.sleep(5)
    run_cmd(client, f"docker ps | grep {DEPLOY_ID[:8]}")
    
    container_name = f"{DEPLOY_ID}-admin-web"
    run_cmd(client, f"docker logs {container_name} --tail=30 2>&1 || docker logs $(docker ps | grep admin-web | grep {DEPLOY_ID[:8]} | awk '{{print $1}}') --tail=30 2>&1")
    
    client.close()
    print("\n=== Deployment script complete ===")


if __name__ == "__main__":
    main()
