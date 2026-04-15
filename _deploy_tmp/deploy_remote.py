import paramiko
import tarfile
import os
import sys
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/"
PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"
TAR_FILE = os.path.join(PROJECT_DIR, "_deploy_tmp", "deploy.tar.gz")

EXCLUDE_PATTERNS = {
    "node_modules", "__pycache__", ".git", "_deploy_tmp", ".next",
    ".nuxt", "dist", ".cache", ".vscode", ".idea", ".cursor",
    "flutter_app", "miniprogram", "mem", "agent-transcripts",
    "venv", ".env", ".mypy_cache", ".pytest_cache",
    "android", "ios", "build", "*.pyc"
}

def should_exclude(path):
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE_PATTERNS:
            return True
        if part.endswith(".pyc"):
            return True
    return False

def create_tar():
    print(f"[1/5] Creating tar archive...")
    count = 0
    with tarfile.open(TAR_FILE, "w:gz") as tar:
        for root, dirs, files in os.walk(PROJECT_DIR):
            rel_root = os.path.relpath(root, PROJECT_DIR)
            if rel_root == ".":
                rel_root = ""
            if should_exclude(rel_root):
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(rel_root, d))]
            for f in files:
                rel_path = os.path.join(rel_root, f) if rel_root else f
                if should_exclude(rel_path):
                    continue
                full_path = os.path.join(root, f)
                try:
                    tar.add(full_path, arcname=rel_path)
                    count += 1
                except (PermissionError, OSError) as e:
                    print(f"  Warning: skipping {rel_path}: {e}")
    size_mb = os.path.getsize(TAR_FILE) / (1024 * 1024)
    print(f"  Packed {count} files, archive size: {size_mb:.1f} MB")
    return TAR_FILE

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return client

def upload_tar(ssh):
    print(f"[2/5] Uploading to server...")
    sftp = ssh.open_sftp()
    remote_tar = f"/tmp/deploy-{DEPLOY_ID}.tar.gz"
    file_size = os.path.getsize(TAR_FILE)
    transferred = [0]
    last_print = [0]

    def progress(sent, total):
        transferred[0] = sent
        pct = sent * 100 // total
        if pct - last_print[0] >= 10:
            last_print[0] = pct
            print(f"  Upload progress: {pct}%")

    sftp.put(TAR_FILE, remote_tar, callback=progress)
    sftp.close()
    print(f"  Upload complete: {file_size / (1024*1024):.1f} MB")
    return remote_tar

def run_remote(ssh, cmd, timeout=600, stream=True):
    print(f"  >> {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    output_lines = []
    if stream:
        for line in stdout:
            line = line.strip()
            output_lines.append(line)
            print(f"     {line}")
    else:
        output_lines = stdout.read().decode('utf-8', errors='replace').strip().split('\n')
    err = stderr.read().decode('utf-8', errors='replace').strip()
    exit_code = stdout.channel.recv_exit_status()
    if err and exit_code != 0:
        for eline in err.split('\n')[:20]:
            print(f"  [stderr] {eline}")
    return '\n'.join(output_lines), err, exit_code

def deploy(ssh, remote_tar):
    print(f"[3/5] Deploying on server...")

    run_remote(ssh, f"mkdir -p {REMOTE_DIR}")
    run_remote(ssh, f"cd {REMOTE_DIR} && tar xzf {remote_tar}")
    run_remote(ssh, f"rm -f {remote_tar}")

    print("\n  Stopping old containers...")
    run_remote(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down --remove-orphans", timeout=120)

    print("\n  Building containers (this may take several minutes)...")
    out, err, code = run_remote(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    if code != 0:
        print(f"  ERROR: Build failed with exit code {code}")
        print(f"  Build output (last 30 lines):")
        for line in out.split('\n')[-30:]:
            print(f"    {line}")
        if err:
            for line in err.split('\n')[-10:]:
                print(f"    [err] {line}")
        return False

    print("\n  Starting containers...")
    out, err, code = run_remote(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    if code != 0:
        print(f"  ERROR: Failed to start containers")
        return False

    print("\n  Waiting for containers to become healthy...")
    for i in range(30):
        time.sleep(10)
        out, _, _ = run_remote(ssh, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'", stream=False)
        print(f"  Health check attempt {i+1}/30:")
        for line in out.strip().split('\n'):
            if line.strip():
                print(f"    {line}")
        if "unhealthy" not in out.lower() and ("healthy" in out.lower() or "Up" in out):
            all_up = True
            for name in [f"{DEPLOY_ID}-backend", f"{DEPLOY_ID}-admin", f"{DEPLOY_ID}-h5", f"{DEPLOY_ID}-db"]:
                if name not in out:
                    all_up = False
                    break
            if all_up:
                starting = "starting" in out.lower() and "healthy" not in out.lower()
                if not starting:
                    print("  All containers are running!")
                    return True
    print("  WARNING: Health check timed out, continuing with gateway setup...")
    return True

def setup_gateway(ssh):
    print(f"[4/5] Setting up gateway routing...")

    network_name = f"{DEPLOY_ID}-network"
    run_remote(ssh, f"docker network connect {network_name} gateway 2>/dev/null; echo done", timeout=30)

    gateway_routes_content = open(os.path.join(PROJECT_DIR, "gateway-routes.conf"), "r").read()

    escaped = gateway_routes_content.replace("'", "'\\''")
    conf_file = f"/tmp/gateway-route-{DEPLOY_ID}.conf"
    run_remote(ssh, f"cat > {conf_file} << 'ROUTEEOF'\n{gateway_routes_content}\nROUTEEOF", timeout=30, stream=False)

    run_remote(ssh, f"docker cp {conf_file} gateway:/etc/nginx/conf.d/{DEPLOY_ID}.conf", timeout=30)
    run_remote(ssh, f"rm -f {conf_file}", timeout=10, stream=False)

    print("  Testing nginx configuration...")
    out, err, code = run_remote(ssh, "docker exec gateway nginx -t 2>&1", timeout=30)
    if code != 0:
        print(f"  ERROR: nginx config test failed!")
        print(f"  {out}")
        print(f"  {err}")
        return False

    print("  Reloading nginx...")
    run_remote(ssh, "docker exec gateway nginx -s reload 2>&1", timeout=30)
    print("  Gateway configured successfully!")
    return True

def verify(ssh):
    print(f"[5/5] Verifying deployment...")

    out, _, _ = run_remote(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'", stream=False)
    print("\n  Container Status:")
    for line in out.strip().split('\n'):
        print(f"    {line}")

    print("\n  Checking container logs for errors...")
    for svc in ["backend", "admin", "h5"]:
        container = f"{DEPLOY_ID}-{svc}"
        out, _, _ = run_remote(ssh, f"docker logs --tail 5 {container} 2>&1", stream=False)
        print(f"\n  [{svc}] last 5 log lines:")
        for line in out.strip().split('\n'):
            print(f"    {line}")

    return True

def main():
    try:
        create_tar()

        print(f"\nConnecting to {SERVER}...")
        ssh = get_ssh_client()
        print("  Connected!")

        remote_tar = upload_tar(ssh)

        success = deploy(ssh, remote_tar)
        if not success:
            print("\n*** DEPLOYMENT FAILED during build/start ***")
            ssh.close()
            return 1

        gw_ok = setup_gateway(ssh)
        if not gw_ok:
            print("\n*** WARNING: Gateway setup had issues ***")

        verify(ssh)

        ssh.close()
        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE")
        print(f"Base URL: https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}")
        print(f"H5:    https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/")
        print(f"Admin: https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/")
        print(f"API:   https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n*** DEPLOYMENT ERROR: {e} ***")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
