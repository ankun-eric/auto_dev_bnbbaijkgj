import paramiko
import os
import sys
import time
import tarfile
import stat

DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
SSH_PORT = 22
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", "__pycache__", ".git", ".pytest_cache",
    "flutter_app", "miniprogram", "verify-miniprogram",
    "ui_design_outputs", ".chat_output", ".consulting_output",
    "uploads", ".cursor", ".github"
}
EXCLUDE_EXTS = {".apk", ".zip", ".tar.gz"}
EXCLUDE_FILES = {
    "deploy_package.tar.gz", "project.tar.gz",
    "deploy_helper.py", "deploy_now.py", "deploy_remote.py",
    "deploy_ssh.py", "deploy_transfer.py", "deploy_upload.py",
    "do_deploy.py", "deploy_exec.py", "deploy_port_check.py",
    "error_screenshot.png"
}

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    print(f"[OK] SSH connected to {SSH_HOST}")
    return client

def run_cmd(client, cmd, timeout=300):
    print(f"[CMD] {cmd[:200]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        for line in out.strip().split("\n")[-30:]:
            print(f"  {line}")
    if err.strip() and exit_code != 0:
        for line in err.strip().split("\n")[-15:]:
            print(f"  [ERR] {line}")
    return exit_code, out, err

def should_exclude(path, name):
    if name in EXCLUDE_DIRS:
        return True
    if name in EXCLUDE_FILES:
        return True
    for ext in EXCLUDE_EXTS:
        if name.endswith(ext):
            return True
    return False

def create_tarball():
    tar_path = os.path.join(PROJECT_DIR, "deploy_bundle.tar.gz")
    print(f"[PACK] Creating tarball...")
    count = 0
    with tarfile.open(tar_path, "w:gz") as tar:
        for root, dirs, files in os.walk(PROJECT_DIR):
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), d)]
            for f in files:
                if should_exclude(os.path.join(root, f), f):
                    continue
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, PROJECT_DIR)
                try:
                    tar.add(full, arcname=arcname)
                    count += 1
                except Exception as e:
                    print(f"  [WARN] Skip {arcname}: {e}")
    size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"[OK] Tarball created: {count} files, {size_mb:.1f} MB")
    return tar_path

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"[UPLOAD] {os.path.basename(local_path)} ({size_mb:.1f} MB) -> {remote_path}")
    sftp.put(local_path, remote_path, callback=lambda sent, total: None)
    print(f"[OK] Upload complete")
    sftp.close()

def upload_file_content(client, content, remote_path):
    sftp = client.open_sftp()
    with sftp.file(remote_path, 'w') as f:
        f.write(content)
    sftp.close()

def main():
    print("=" * 60)
    print(f"DEPLOYING: {DEPLOY_ID}")
    print("=" * 60)

    # Step 1: Connect and check environment
    print("\n--- Step 1: Connect & Check Environment ---")
    client = create_ssh_client()
    code, out, err = run_cmd(client, "docker --version && docker compose version")
    if code != 0:
        print("[FAIL] Docker not available on server")
        sys.exit(1)
    print("[OK] Docker environment ready")

    # Step 2: Package and transfer
    print("\n--- Step 2: Package & Transfer ---")
    tar_path = create_tarball()

    run_cmd(client, f"mkdir -p {REMOTE_DIR}")
    remote_tar = f"{REMOTE_DIR}/deploy_bundle.tar.gz"
    upload_file(client, tar_path, remote_tar)

    print("[EXTRACT] Extracting on server...")
    code, out, err = run_cmd(client, f"cd {REMOTE_DIR} && tar xzf deploy_bundle.tar.gz && rm deploy_bundle.tar.gz && echo 'EXTRACT_OK'")
    if "EXTRACT_OK" not in out:
        print("[FAIL] Extraction failed")
        sys.exit(1)
    print("[OK] Files extracted")

    # Clean up local tarball
    try:
        os.remove(tar_path)
    except:
        pass

    # Step 3: Build and start containers
    print("\n--- Step 3: Build & Start Containers ---")
    compose_cmd = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml"

    print("[STOP] Stopping old containers...")
    run_cmd(client, f"{compose_cmd} down --remove-orphans 2>/dev/null || true", timeout=60)

    print("[BUILD] Building containers (this may take a few minutes)...")
    code, out, err = run_cmd(client, f"{compose_cmd} build --no-cache 2>&1", timeout=600)
    if code != 0:
        print(f"[FAIL] Build failed with exit code {code}")
        print(f"Last error: {err[-500:] if err else out[-500:]}")
        sys.exit(1)
    print("[OK] Build complete")

    print("[START] Starting containers...")
    code, out, err = run_cmd(client, f"{compose_cmd} up -d 2>&1", timeout=120)
    if code != 0:
        print(f"[FAIL] Start failed")
        sys.exit(1)
    print("[OK] Containers started")

    # Wait for containers to be ready
    print("[WAIT] Waiting for containers to be healthy...")
    for i in range(30):
        time.sleep(5)
        code, out, err = run_cmd(client, f"{compose_cmd} ps --format '{{{{.Name}}}} {{{{.Status}}}}'")
        if "unhealthy" not in out.lower() and ("healthy" in out.lower() or i >= 5):
            all_up = True
            for svc in ["backend", "admin", "h5", "db"]:
                if f"{DEPLOY_ID}-{svc}" not in out:
                    all_up = False
                    break
            if all_up and "starting" not in out.lower():
                break
        print(f"  Waiting... ({(i+1)*5}s)")
    
    print("[STATUS] Container status:")
    run_cmd(client, f"{compose_cmd} ps")

    # Step 4: Update gateway-nginx
    print("\n--- Step 4: Update Gateway Nginx ---")
    
    gateway_conf_path = os.path.join(PROJECT_DIR, "gateway-routes.conf")
    with open(gateway_conf_path, "r", encoding="utf-8") as f:
        gateway_conf_content = f.read()

    conf_remote = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
    run_cmd(client, "mkdir -p /home/ubuntu/gateway/conf.d")
    
    # Backup existing conf
    run_cmd(client, f"cp {conf_remote} {conf_remote}.bak 2>/dev/null || true")
    
    upload_file_content(client, gateway_conf_content, conf_remote)
    print(f"[OK] Gateway config uploaded to {conf_remote}")

    # Connect gateway to project network
    print("[NET] Connecting gateway to project network...")
    for gw_name in ["gateway-nginx", "gateway"]:
        run_cmd(client, f"docker network connect {DEPLOY_ID}-network {gw_name} 2>/dev/null || true")

    # Test nginx config
    print("[TEST] Testing nginx configuration...")
    for gw_name in ["gateway-nginx", "gateway"]:
        code, out, err = run_cmd(client, f"docker exec {gw_name} nginx -t 2>&1")
        if code == 0:
            print(f"[OK] Nginx config test passed ({gw_name})")
            # Reload nginx
            print("[RELOAD] Reloading nginx...")
            code2, out2, err2 = run_cmd(client, f"docker exec {gw_name} nginx -s reload 2>&1")
            if code2 == 0:
                print("[OK] Nginx reloaded successfully")
            else:
                print(f"[WARN] Nginx reload issue: {err2}")
            break
    else:
        print("[WARN] Could not test nginx - checking both gateway names failed")

    # Step 5: Verify deployment
    print("\n--- Step 5: Verify Deployment ---")
    time.sleep(5)

    urls = [
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health",
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/",
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/",
    ]

    results = {}
    for url in urls:
        code, out, err = run_cmd(client, f"curl -skL -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'")
        http_code = out.strip().replace("'", "")
        status = "OK" if http_code.startswith("2") or http_code == "307" or http_code == "308" else "FAIL"
        results[url] = (http_code, status)
        print(f"  [{status}] {http_code} - {url}")

    # Final container status
    print("\n--- Final Container Status ---")
    run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")

    # Check container logs for errors
    print("\n--- Recent Backend Logs ---")
    run_cmd(client, f"docker logs {DEPLOY_ID}-backend --tail 15 2>&1")

    client.close()

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    all_ok = all(v[1] == "OK" for v in results.values())
    print(f"Status: {'SUCCESS' if all_ok else 'PARTIAL - Some URLs may need time to initialize'}")
    for url, (code, status) in results.items():
        print(f"  [{status}] {code} - {url}")
    print("=" * 60)

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
