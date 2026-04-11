#!/usr/bin/env python3
"""Deploy admin-web by copying files into existing container and rebuilding inside."""
import paramiko
import os
import tarfile
import time

HOST = "newbb.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
SERVER_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ADMIN_WEB = r"C:\auto_output\bnbbaijkgj\admin-web"
TAR_NAME = "admin_web_src.tar.gz"
LOCAL_TAR = rf"C:\auto_output\bnbbaijkgj\{TAR_NAME}"
CONTAINER_NAME = f"{DEPLOY_ID}-admin"


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def run_cmd(client, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    return out, err


def pack_src_only():
    """Pack only source files, excluding node_modules and .next."""
    print(f"\n=== Packing admin-web source files ===")
    excludes = {'node_modules', '.next', '.git', '__pycache__', '.env.local', 'tsconfig.tsbuildinfo'}
    
    with tarfile.open(LOCAL_TAR, 'w:gz') as tar:
        for root, dirs, files in os.walk(LOCAL_ADMIN_WEB):
            dirs[:] = [d for d in dirs if d not in excludes]
            for file in files:
                if file == 'tsconfig.tsbuildinfo':
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, LOCAL_ADMIN_WEB)
                tar.add(filepath, arcname=arcname)
    
    size = os.path.getsize(LOCAL_TAR)
    print(f"Created {LOCAL_TAR} ({size/1024:.1f} KB)")


def upload_file(client, local_path, remote_path):
    print(f"\n=== Uploading {os.path.basename(local_path)} ===")
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("Upload complete.")


def main():
    # Pack source files only
    pack_src_only()
    
    # Connect to server
    print(f"\n=== Connecting to {HOST} ===")
    client = ssh_connect()
    print("Connected!")
    
    # Check container status
    print("\n=== Check container status ===")
    run_cmd(client, f"docker ps --format 'table {{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID[:8]}")
    
    # Upload source tar to server
    remote_tar = f"/tmp/{TAR_NAME}"
    upload_file(client, LOCAL_TAR, remote_tar)
    
    # Copy source into container and rebuild
    print("\n=== Copy source files into container ===")
    run_cmd(client, f"docker cp {remote_tar} {CONTAINER_NAME}:/tmp/{TAR_NAME}")
    
    # Extract inside container, preserving node_modules
    print("\n=== Extract source inside container ===")
    run_cmd(client, f"docker exec {CONTAINER_NAME} sh -c 'cd /app && tar -xzf /tmp/{TAR_NAME}'")
    
    # Run next build inside container
    print("\n=== Run next build inside container ===")
    out, err = run_cmd(client, 
        f"docker exec {CONTAINER_NAME} sh -c 'cd /app && npm run build 2>&1'",
        timeout=600)
    
    if "error" in out.lower() or "error" in err.lower():
        if "Failed to compile" in out or "Build failed" in out:
            print("\nERROR: Build failed!")
            client.close()
            return False
    
    # Restart the container to pick up new build
    print("\n=== Restart admin-web container ===")
    run_cmd(client, f"docker restart {CONTAINER_NAME}")
    
    # Wait for container to start
    time.sleep(10)
    
    # Verify
    print("\n=== Verify container status ===")
    run_cmd(client, f"docker ps | grep {DEPLOY_ID[:8]}")
    run_cmd(client, f"docker logs {CONTAINER_NAME} --tail=20")
    
    # Health check
    print("\n=== Health check ===")
    base_url = f"https://{HOST}/autodev/{DEPLOY_ID}"
    run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {base_url}/admin/ --max-time 30")
    run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {base_url}/api/health --max-time 30")
    
    client.close()
    print("\n=== Deployment complete ===")
    return True


if __name__ == "__main__":
    main()
