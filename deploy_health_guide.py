#!/usr/bin/env python3
"""Deploy health guide feature to remote server."""

import os
import sys
import time
import tarfile
import paramiko
from pathlib import Path

# Config
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"
BASE_URL_PATH = f"/autodev/{DEPLOY_ID}"


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return client


def run_ssh(client, cmd, timeout=120):
    print(f"  $ {cmd[:100]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  OUT: {out.strip()[:500]}")
    if err.strip() and exit_code != 0:
        print(f"  ERR: {err.strip()[:500]}")
    return exit_code, out, err


def create_tar(local_dir, output_path, dirs_to_include):
    """Create tar of specified directories."""
    excludes = {"node_modules", "__pycache__", ".git", ".next", ".pytest_cache", "*.pyc"}
    
    def should_exclude(path):
        parts = Path(path).parts
        for part in parts:
            if part in excludes or part.endswith(".pyc"):
                return True
        return False
    
    with tarfile.open(output_path, "w:gz") as tar:
        for d in dirs_to_include:
            full_path = os.path.join(local_dir, d)
            if os.path.exists(full_path):
                print(f"  Adding {d}...")
                for root, dirs, files in os.walk(full_path):
                    # Filter excluded dirs in-place
                    dirs[:] = [dd for dd in dirs if dd not in excludes]
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, local_dir)
                        if not should_exclude(arcname):
                            tar.add(file_path, arcname=arcname)
            else:
                print(f"  Skipping {d} (not found)")
        
        # Add root-level files
        for fname in ["docker-compose.prod.yml", ".env.production", ".env", "gateway-routes.conf"]:
            fpath = os.path.join(local_dir, fname)
            if os.path.exists(fpath):
                print(f"  Adding {fname}...")
                tar.add(fpath, arcname=fname)


def upload_file(sftp, local_path, remote_path):
    print(f"  Uploading {os.path.basename(local_path)} -> {remote_path}")
    sftp.put(local_path, remote_path)


def main():
    print("=" * 60)
    print("DEPLOY: Health Guide Feature")
    print(f"DEPLOY_ID: {DEPLOY_ID}")
    print("=" * 60)

    # Step 1: Connect
    print("\n[1] Connecting to server...")
    client = get_ssh_client()
    print("  Connected!")

    # Step 2: Check existing containers
    print("\n[2] Checking existing containers...")
    _, out, _ = run_ssh(client, f"docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID}")
    if out.strip():
        print(f"  Existing containers: {out.strip()}")
    else:
        print("  No existing containers found")

    # Step 3: Create remote directory
    print("\n[3] Creating remote directory...")
    run_ssh(client, f"mkdir -p {REMOTE_DIR}")

    # Step 4: Create tar archive locally
    print("\n[4] Creating archive...")
    tar_path = os.path.join(LOCAL_DIR, "_deploy_tmp", "deploy_health_guide.tar.gz")
    os.makedirs(os.path.dirname(tar_path), exist_ok=True)
    create_tar(LOCAL_DIR, tar_path, ["backend", "h5-web", "admin-web"])
    print(f"  Archive created: {os.path.getsize(tar_path) / 1024 / 1024:.1f} MB")

    # Step 5: Upload archive
    print("\n[5] Uploading archive...")
    sftp = client.open_sftp()
    remote_tar = f"{REMOTE_DIR}/deploy.tar.gz"
    upload_file(sftp, tar_path, remote_tar)
    sftp.close()
    print("  Upload complete!")

    # Step 6: Extract on server
    print("\n[6] Extracting archive on server...")
    rc, out, err = run_ssh(client, f"cd {REMOTE_DIR} && tar -xzf deploy.tar.gz && rm deploy.tar.gz")
    if rc != 0:
        print(f"  ERROR extracting: {err}")
        sys.exit(1)
    print("  Extracted!")

    # Step 7: Stop existing containers
    print("\n[7] Stopping existing containers...")
    run_ssh(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=60)

    # Step 8: Build containers
    print("\n[8] Building containers (this may take a while)...")
    rc, out, err = run_ssh(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1 | tail -50",
        timeout=600)
    if rc != 0:
        print(f"  BUILD FAILED!")
        print(f"  {err[:2000]}")
        # Get full logs
        run_ssh(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build 2>&1 | tail -100", timeout=600)
        sys.exit(1)
    print("  Build complete!")

    # Step 9: Start containers
    print("\n[9] Starting containers...")
    rc, out, err = run_ssh(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1",
        timeout=120)
    if rc != 0:
        print(f"  START FAILED: {err}")
        sys.exit(1)
    print("  Containers started!")

    # Step 10: Wait for containers to be healthy
    print("\n[10] Waiting for containers to be ready (30s)...")
    time.sleep(30)

    # Step 11: Check container status
    print("\n[11] Checking container status...")
    _, out, _ = run_ssh(client, f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}")
    print(f"  {out.strip()}")

    # Step 12: Run database migration
    print("\n[12] Running database migration (add guide_count column)...")
    migration_cmd = f"""docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def migrate():
    async with engine.begin() as conn:
        try:
            await conn.execute(text('ALTER TABLE health_profiles ADD COLUMN guide_count INT NOT NULL DEFAULT 0'))
            print('Migration successful: guide_count column added')
        except Exception as e:
            if 'Duplicate column' in str(e) or 'already exists' in str(e):
                print('Column already exists, skipping')
            else:
                print(f'Migration error: {{e}}')

asyncio.run(migrate())
" """
    rc, out, err = run_ssh(client, migration_cmd, timeout=60)
    print(f"  Migration result: {out.strip()}")

    # Step 13: Check backend health
    print("\n[13] Checking backend health...")
    rc, out, err = run_ssh(client, 
        f"docker exec {DEPLOY_ID}-backend curl -s http://localhost:8000/api/health 2>&1 | head -5")
    print(f"  Backend health: {out.strip()[:200]}")

    # Step 14: Check container logs for errors
    print("\n[14] Checking container logs...")
    run_ssh(client, f"docker logs {DEPLOY_ID}-backend --tail=20 2>&1")
    run_ssh(client, f"docker logs {DEPLOY_ID}-h5 --tail=10 2>&1")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 60)
    client.close()


if __name__ == "__main__":
    main()
