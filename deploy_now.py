import paramiko
import subprocess
import os
import sys
import time

SERVER = "newbb.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = [
    "node_modules", ".next", ".git", "__pycache__", ".pytest_cache",
    "flutter_app", "miniprogram", "verify-miniprogram",
    "ui_design_outputs", ".chat_output", ".consulting_output",
    "uploads", ".cursor", ".github",
]
EXCLUDE_FILES = [
    "*.apk", "*.zip", "*.tar.gz", "*.pyc", "deploy_package.tar.gz",
    "error_screenshot.png", "gen_*.py", "ui_generator_common.py",
    "deploy_helper.py", "deploy_port_check.py", "deploy_upload.py",
    "test_*.py", "att*.txt", "doc*.txt", "*.docx",
]


def ssh_exec(client, cmd, timeout=300):
    print(f"  [SSH] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(f"  [OUT] {out.strip()[:2000]}")
    if err.strip():
        print(f"  [ERR] {err.strip()[:2000]}")
    return exit_code, out, err


def create_tar():
    tar_path = os.path.join(LOCAL_DIR, "deploy_package.tar.gz")
    excludes = []
    for d in EXCLUDE_DIRS:
        excludes.append(f"--exclude=./{d}")
    for f in EXCLUDE_FILES:
        excludes.append(f"--exclude={f}")
    
    exclude_str = " ".join(excludes)
    cmd = f'tar czf deploy_package.tar.gz {exclude_str} -C "{LOCAL_DIR}" ./backend ./admin-web ./h5-web ./docker-compose.prod.yml ./.env ./.dockerignore ./nginx.conf ./gateway-routes.conf ./project-context.mdc ./pytest.ini'
    print(f"Creating tar package...")
    print(f"  Command: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=LOCAL_DIR, timeout=120)
    if result.returncode != 0:
        print(f"  tar stderr: {result.stderr}")
        if not os.path.exists(tar_path):
            raise Exception(f"Failed to create tar: {result.stderr}")
    
    size = os.path.getsize(tar_path)
    print(f"  Package created: {size / 1024 / 1024:.1f} MB")
    return tar_path


def upload_and_extract(client, tar_path):
    sftp = client.open_sftp()
    remote_tar = f"/home/ubuntu/deploy_package_{DEPLOY_ID}.tar.gz"
    
    size = os.path.getsize(tar_path)
    print(f"Uploading {size / 1024 / 1024:.1f} MB to server...")
    
    start = time.time()
    sftp.put(tar_path, remote_tar)
    elapsed = time.time() - start
    print(f"  Upload completed in {elapsed:.1f}s")
    sftp.close()
    
    print("Extracting on server...")
    ssh_exec(client, f"mkdir -p {REMOTE_DIR}")
    ssh_exec(client, f"tar xzf {remote_tar} -C {REMOTE_DIR}")
    ssh_exec(client, f"rm -f {remote_tar}")
    print("  Extraction complete")


def rebuild_containers(client):
    print("Stopping existing containers...")
    ssh_exec(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down", timeout=120)
    
    print("Building backend and admin-web (this may take a few minutes)...")
    exit_code, out, err = ssh_exec(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend admin-web 2>&1",
        timeout=600)
    if exit_code != 0:
        print(f"WARNING: Build may have issues (exit code {exit_code})")
    
    print("Starting all containers...")
    exit_code, out, err = ssh_exec(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1",
        timeout=120)
    if exit_code != 0:
        print(f"WARNING: Up may have issues (exit code {exit_code})")
    
    time.sleep(5)
    
    print("Checking container status...")
    exit_code, out, err = ssh_exec(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")
    return out


def check_gateway(client):
    print("Checking gateway configuration...")
    ssh_exec(client, "docker ps --filter name=gateway-nginx --format '{{.Names}} {{.Status}}'")
    
    exit_code, out, err = ssh_exec(client, "docker exec gateway-nginx cat /etc/nginx/conf.d/routes.conf 2>/dev/null | head -50")
    if DEPLOY_ID in out:
        print("  Gateway routes contain our deploy ID - OK")
    else:
        print("  Gateway routes may need updating, checking...")
        exit_code2, out2, err2 = ssh_exec(client, "docker exec gateway-nginx ls /etc/nginx/conf.d/")
        print(f"  Nginx conf files: {out2.strip()}")
        
        if os.path.exists(os.path.join(LOCAL_DIR, "gateway-routes.conf")):
            print("  Uploading gateway-routes.conf...")
            sftp = client.open_sftp()
            sftp.put(os.path.join(LOCAL_DIR, "gateway-routes.conf"), f"/home/ubuntu/gateway-routes-{DEPLOY_ID}.conf")
            sftp.close()
            ssh_exec(client, f"docker cp /home/ubuntu/gateway-routes-{DEPLOY_ID}.conf gateway-nginx:/etc/nginx/conf.d/routes-{DEPLOY_ID}.conf")
            ssh_exec(client, "docker exec gateway-nginx nginx -t")
            ssh_exec(client, "docker exec gateway-nginx nginx -s reload")
            print("  Gateway updated")


def main():
    print("=" * 60)
    print(f"Deploying {DEPLOY_ID}")
    print("=" * 60)
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print("\n[Step 1] Connecting to server...")
    client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    print("  Connected successfully!")
    
    print("\n[Step 2] Creating deployment package...")
    tar_path = create_tar()
    
    print("\n[Step 3] Uploading and extracting...")
    upload_and_extract(client, tar_path)
    
    print("\n[Step 4] Rebuilding containers...")
    container_status = rebuild_containers(client)
    
    print("\n[Step 5] Checking gateway...")
    check_gateway(client)
    
    print("\n[Step 6] Waiting for services to start (30s)...")
    time.sleep(30)
    
    print("Final container status:")
    ssh_exec(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")
    
    print("\nChecking container logs for errors...")
    ssh_exec(client, f"docker logs {DEPLOY_ID}-backend --tail 20 2>&1")
    
    client.close()
    print("\n" + "=" * 60)
    print("Deployment script completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
