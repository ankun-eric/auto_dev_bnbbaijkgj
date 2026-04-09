#!/usr/bin/env python3
"""Deploy notice feature to remote server."""
import paramiko
import os
import tarfile
import time
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client

def run_cmd(client, cmd, timeout=300):
    print(f"  $ {cmd[:100]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  OUT: {out.strip()[:500]}")
    if err.strip() and rc != 0:
        print(f"  ERR: {err.strip()[:500]}")
    return rc, out, err

def create_archive():
    """Create tar.gz of changed files."""
    archive_path = os.path.join(LOCAL_DIR, "_deploy_tmp", "notice_deploy.tar.gz")
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    
    print("Creating deployment archive...")
    
    def should_exclude(path):
        excludes = ['__pycache__', '.pyc', 'node_modules', '.next', '.env']
        for ex in excludes:
            if ex in path:
                return True
        return False
    
    with tarfile.open(archive_path, 'w:gz') as tar:
        # backend
        backend_dir = os.path.join(LOCAL_DIR, "backend")
        for root, dirs, files in os.walk(backend_dir):
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            for file in files:
                if should_exclude(file):
                    continue
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, LOCAL_DIR)
                tar.add(full_path, arcname=arcname)
        
        # admin-web
        admin_dir = os.path.join(LOCAL_DIR, "admin-web")
        for root, dirs, files in os.walk(admin_dir):
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            for file in files:
                if should_exclude(file):
                    continue
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, LOCAL_DIR)
                tar.add(full_path, arcname=arcname)
        
        # h5-web
        h5_dir = os.path.join(LOCAL_DIR, "h5-web")
        for root, dirs, files in os.walk(h5_dir):
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            for file in files:
                if should_exclude(file):
                    continue
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, LOCAL_DIR)
                tar.add(full_path, arcname=arcname)
        
        # docker-compose.prod.yml
        dc_file = os.path.join(LOCAL_DIR, "docker-compose.prod.yml")
        tar.add(dc_file, arcname="docker-compose.prod.yml")
    
    size = os.path.getsize(archive_path)
    print(f"Archive created: {archive_path} ({size/1024/1024:.1f} MB)")
    return archive_path

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    print(f"Uploading {os.path.basename(local_path)} to {remote_path}...")
    sftp.put(local_path, remote_path)
    sftp.close()
    print("Upload complete.")

def main():
    print("=" * 60)
    print("STEP 1: Creating deployment archive")
    print("=" * 60)
    archive_path = create_archive()
    
    print("\n" + "=" * 60)
    print("STEP 2: Connecting to server and uploading")
    print("=" * 60)
    client = create_ssh_client()
    print(f"Connected to {HOST}")
    
    # Ensure remote dir exists
    run_cmd(client, f"mkdir -p {REMOTE_DIR}")
    
    # Upload archive
    remote_archive = f"{REMOTE_DIR}/notice_deploy.tar.gz"
    upload_file(client, archive_path, remote_archive)
    
    print("\n" + "=" * 60)
    print("STEP 3: Extracting files on server")
    print("=" * 60)
    rc, out, err = run_cmd(client, f"cd {REMOTE_DIR} && tar -xzf notice_deploy.tar.gz && rm notice_deploy.tar.gz")
    if rc != 0:
        print(f"ERROR: Failed to extract archive: {err}")
        client.close()
        sys.exit(1)
    print("Files extracted successfully.")
    
    # Verify key files
    print("\nVerifying key files...")
    run_cmd(client, f"ls {REMOTE_DIR}/backend/app/api/notice.py {REMOTE_DIR}/backend/app/schemas/notice.py 2>&1")
    run_cmd(client, f"ls {REMOTE_DIR}/admin-web/src/app/\\(admin\\)/notices/ 2>&1")
    
    print("\n" + "=" * 60)
    print("STEP 4: Building containers")
    print("=" * 60)
    print("Building backend...")
    rc, out, err = run_cmd(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -20",
        timeout=600)
    if rc != 0:
        print(f"Backend build failed! Checking logs...")
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -50", timeout=600)
    
    print("\nBuilding h5-web...")
    rc, out, err = run_cmd(client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -20",
        timeout=600)
    
    print("\nBuilding admin-web...")
    rc, out, err = run_cmd(client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1 | tail -20",
        timeout=600)
    
    print("\n" + "=" * 60)
    print("STEP 5: Starting containers")
    print("=" * 60)
    rc, out, err = run_cmd(client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1",
        timeout=120)
    print(f"docker compose up: rc={rc}")
    
    print("\nWaiting 30s for containers to start...")
    time.sleep(30)
    
    print("\n" + "=" * 60)
    print("STEP 6: Checking container status")
    print("=" * 60)
    rc, out, err = run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1")
    print(out)
    
    client.close()
    print("\nDeployment script completed.")

if __name__ == "__main__":
    main()
