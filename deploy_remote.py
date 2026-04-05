import paramiko
import os
import sys
import time
import stat
import tarfile
import io

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PORT = 22
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", "__pycache__", ".git", ".next", ".cursor",
    ".pytest_cache", "ui_design_outputs", "verify-miniprogram",
    "flutter_app", "miniprogram", "agent-transcripts",
    ".chat_output", ".consulting_output", ".github",
}

EXCLUDE_EXTENSIONS = {".apk", ".zip", ".pyc"}

EXCLUDE_FILES = {"deploy_package.tar.gz", "deploy_remote.py"}

EXCLUDE_PREFIXES = {"bini_health_android", "miniprogram_"}


def should_exclude(path, name, is_dir=False):
    if is_dir:
        if name in EXCLUDE_DIRS:
            return True
        rel = os.path.relpath(path, PROJECT_DIR).replace("\\", "/")
        excluded_paths = [
            "h5-web/node_modules", "admin-web/node_modules",
            "admin-web/.next", "h5-web/.next",
        ]
        for ep in excluded_paths:
            if rel == ep or rel.startswith(ep + "/"):
                return True
        return False
    if name in EXCLUDE_FILES:
        return True
    for prefix in EXCLUDE_PREFIXES:
        if name.startswith(prefix):
            return True
    _, ext = os.path.splitext(name)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return True
    fpath = os.path.join(os.path.dirname(path), name) if not os.path.isabs(path) else path
    try:
        if os.path.getsize(fpath) > 10 * 1024 * 1024:
            return True
    except OSError:
        pass
    return False


def create_tar(project_dir):
    print("[TAR] Creating tar archive of project files...")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), d, is_dir=True)]
            for f in files:
                full_path = os.path.join(root, f)
                if should_exclude(full_path, f, is_dir=False):
                    continue
                arcname = os.path.relpath(full_path, project_dir).replace("\\", "/")
                try:
                    tar.add(full_path, arcname=arcname)
                except (PermissionError, OSError) as e:
                    print(f"  [WARN] Skipping {arcname}: {e}")
    buf.seek(0)
    size_mb = len(buf.getvalue()) / (1024 * 1024)
    print(f"[TAR] Archive size: {size_mb:.2f} MB")
    return buf


def connect_ssh():
    print(f"[SSH] Connecting to {SERVER}:{PORT}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("[SSH] Connected successfully!")
    return client


def exec_cmd(client, cmd, timeout=300, check=False):
    print(f"[CMD] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(f"  [OUT] {out.strip()[:2000]}")
    if err.strip():
        print(f"  [ERR] {err.strip()[:2000]}")
    print(f"  [EXIT] {exit_code}")
    if check and exit_code != 0:
        raise RuntimeError(f"Command failed with exit code {exit_code}: {cmd}\n{err}")
    return exit_code, out, err


def main():
    ssh = connect_ssh()

    # Test connectivity
    exec_cmd(ssh, "echo 'Server OK' && uname -a && docker --version && docker compose version", check=True)

    # Prepare remote directory
    print("\n=== Step 2: Transfer project files ===")
    exec_cmd(ssh, f"mkdir -p {REMOTE_DIR}")

    tar_buf = create_tar(PROJECT_DIR)

    local_tar = os.path.join(PROJECT_DIR, "deploy_upload.tar.gz")
    with open(local_tar, "wb") as f:
        f.write(tar_buf.getvalue())
    print(f"[TAR] Saved locally: {local_tar}")

    print("[SCP] Uploading archive to server...")
    sftp = ssh.open_sftp()
    remote_tar = f"{REMOTE_DIR}/deploy_upload.tar.gz"
    sftp.put(local_tar, remote_tar)
    print("[SCP] Upload complete!")
    sftp.close()

    os.remove(local_tar)
    print("[TAR] Cleaned up local archive")

    print("[EXTRACT] Extracting archive on server...")
    exec_cmd(ssh, f"cd {REMOTE_DIR} && tar xzf deploy_upload.tar.gz && rm deploy_upload.tar.gz", timeout=120, check=True)

    # Build and start Docker containers
    print("\n=== Step 3: Build and start Docker containers ===")
    exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down 2>/dev/null || true", timeout=60)
    
    print("[BUILD] Building Docker images (this may take a few minutes)...")
    exit_code, out, err = exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    if exit_code != 0:
        print(f"[ERROR] Docker build failed!")
        sys.exit(1)

    print("[START] Starting containers...")
    exit_code, out, err = exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    if exit_code != 0:
        print(f"[ERROR] Docker start failed!")
        sys.exit(1)

    print("[WAIT] Waiting for containers to stabilize (30s)...")
    time.sleep(30)

    exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")

    # Update gateway-nginx configuration
    print("\n=== Step 4: Update gateway-nginx configuration ===")
    
    # Check gateway container exists
    exit_code, out, _ = exec_cmd(ssh, "docker ps --filter name=gateway --format '{{.Names}}'")
    if "gateway" not in out:
        print("[WARN] Gateway container not found, checking all containers...")
        exec_cmd(ssh, "docker ps --format '{{.Names}}'")

    # Check if conf.d directory exists in gateway
    exec_cmd(ssh, "docker exec gateway ls -la /etc/nginx/conf.d/ 2>/dev/null || echo 'conf.d not found'")

    # Backup current gateway config
    exec_cmd(ssh, "docker exec gateway cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak 2>/dev/null || true")

    # Copy gateway-routes.conf to gateway container
    routes_src = f"{REMOTE_DIR}/gateway-routes.conf"
    routes_dst = f"/etc/nginx/conf.d/{DEPLOY_ID}.conf"
    exec_cmd(ssh, f"docker cp {routes_src} gateway:{routes_dst}", check=True)
    
    # Connect gateway to project network
    network_name = f"{DEPLOY_ID}-network"
    exec_cmd(ssh, f"docker network connect {network_name} gateway 2>/dev/null || true")
    
    # Test nginx config
    exit_code, out, err = exec_cmd(ssh, "docker exec gateway nginx -t 2>&1")
    if exit_code != 0:
        print("[ERROR] Nginx config test failed!")
        print(f"Output: {out}\n{err}")
        # Try to diagnose
        exec_cmd(ssh, f"docker exec gateway cat {routes_dst}")
        sys.exit(1)

    # Reload nginx
    exec_cmd(ssh, "docker exec gateway nginx -s reload", check=True)

    # Verify SSL
    exec_cmd(ssh, 'curl -vI https://newbb.test.bangbangvip.com/ 2>&1 | grep -iE "SSL|certificate"')

    # Health checks
    print("\n=== Step 5: Health checks ===")
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    
    urls = [
        f"{base_url}/api/health",
        f"{base_url}/admin/",
    ]
    
    all_ok = True
    for url in urls:
        print(f"\n[CHECK] {url}")
        exit_code, out, err = exec_cmd(ssh, f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'")
        http_code = out.strip().strip("'")
        if http_code.startswith("2") or http_code.startswith("3"):
            print(f"  [OK] HTTP {http_code}")
        else:
            print(f"  [FAIL] HTTP {http_code}")
            exec_cmd(ssh, f"curl -sS --max-time 10 '{url}' 2>&1 | head -50")
            all_ok = False

    if not all_ok:
        print("\n=== Step 6: Diagnosing failures ===")
        exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")
        exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs --tail=100 2>&1")

    # Final summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    
    # Container status
    _, container_status, _ = exec_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps --format 'table {{{{.Name}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")
    
    print(f"\nDeploy ID: {DEPLOY_ID}")
    print(f"Base URL: {base_url}")
    print(f"API Health: {base_url}/api/health")
    print(f"Admin Panel: {base_url}/admin/")
    print(f"H5 Frontend: {base_url}/")
    print(f"Deployment Status: {'SUCCESS' if all_ok else 'NEEDS ATTENTION'}")
    print("=" * 60)

    ssh.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
