import paramiko
import os
import sys
import time

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_TAR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deploy_changes.tar.gz")

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return client

def run_cmd(client, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out[:2000])
    if err:
        print(f"STDERR: {err[:2000]}")
    print(f"Exit code: {exit_code}")
    return out, err, exit_code

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    print(f"\nUploading {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)
    stat = sftp.stat(remote_path)
    print(f"Uploaded successfully, size: {stat.st_size} bytes")
    sftp.close()

def main():
    print("=" * 60)
    print("STEP 1: Upload changed files to server")
    print("=" * 60)
    
    client = create_ssh_client()
    print("SSH connected successfully")
    
    remote_tar = f"{REMOTE_DIR}/deploy_changes.tar.gz"
    upload_file(client, LOCAL_TAR, remote_tar)
    
    run_cmd(client, f"cd {REMOTE_DIR} && tar -xzf deploy_changes.tar.gz && rm deploy_changes.tar.gz")
    run_cmd(client, f"ls -la {REMOTE_DIR}/backend/app/api/products.py")
    
    print("\n" + "=" * 60)
    print("STEP 2: Rebuild and restart containers")
    print("=" * 60)
    
    out, err, code = run_cmd(client, f"cd {REMOTE_DIR} && docker-compose build backend h5-web", timeout=300)
    if code != 0:
        print("WARNING: docker-compose build failed, trying docker compose (v2)...")
        out, err, code = run_cmd(client, f"cd {REMOTE_DIR} && docker compose build backend h5-web", timeout=300)
    
    build_cmd = "docker-compose" if code == 0 else "docker compose"
    out, err, code = run_cmd(client, f"cd {REMOTE_DIR} && {build_cmd} up -d backend h5-web", timeout=120)
    
    print("\nWaiting 10 seconds for containers to start...")
    time.sleep(10)
    
    run_cmd(client, f"cd {REMOTE_DIR} && {build_cmd} ps")
    
    print("\n" + "=" * 60)
    print("STEP 3: Verify deployment")
    print("=" * 60)
    
    base_url = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
    
    urls = [
        f"{base_url}/api/products/categories",
        f"{base_url}/api/products?category_id=recommend",
        f"{base_url}/",
    ]
    
    for url in urls:
        print(f"\n--- Checking: {url}")
        out, err, code = run_cmd(client, f'curl -s -o /tmp/resp.txt -w "HTTP_STATUS:%{{http_code}}" "{url}" && echo "" && head -c 500 /tmp/resp.txt')
    
    client.close()
    print("\n" + "=" * 60)
    print("Deployment complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
