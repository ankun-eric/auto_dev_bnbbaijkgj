import paramiko
import tarfile
import os
import sys
import time
import io

SERVER = 'newbb.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

EXCLUDE_DIRS = {
    'node_modules', '.git', '__pycache__', '.next', '.pytest_cache',
    'flutter_app', 'miniprogram', 'verify-miniprogram', 'ui_design_outputs',
}
EXCLUDE_EXTENSIONS = {'.apk', '.zip', '.tar.gz'}
EXCLUDE_FILES = {'deploy_package.tar.gz', 'do_deploy.py'}

INCLUDE_ITEMS = ['backend', 'admin-web', 'h5-web', 'docker-compose.prod.yml', 'gateway-routes.conf', '.env']

def should_exclude(path, name):
    if name in EXCLUDE_DIRS:
        return True
    if name in EXCLUDE_FILES:
        return True
    for ext in EXCLUDE_EXTENSIONS:
        if name.endswith(ext):
            return True
    return False

def create_tar():
    tar_path = os.path.join(LOCAL_DIR, 'deploy_package.tar.gz')
    print(f"[PACK] Creating {tar_path}...")
    with tarfile.open(tar_path, 'w:gz') as tar:
        for item in INCLUDE_ITEMS:
            item_path = os.path.join(LOCAL_DIR, item)
            if os.path.isfile(item_path):
                print(f"  Adding file: {item}")
                tar.add(item_path, arcname=item)
            elif os.path.isdir(item_path):
                print(f"  Adding dir: {item}")
                for root, dirs, files in os.walk(item_path):
                    dirs[:] = [d for d in dirs if not should_exclude(root, d)]
                    for f in files:
                        if not should_exclude(root, f):
                            fp = os.path.join(root, f)
                            arcname = os.path.relpath(fp, LOCAL_DIR)
                            tar.add(fp, arcname=arcname)
            else:
                print(f"  WARN: {item} not found, skipping")
    size_mb = os.path.getsize(tar_path) / (1024*1024)
    print(f"[PACK] Done. Size: {size_mb:.1f} MB")
    return tar_path

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, timeout=600):
    print(f"[SSH] $ {cmd[:120]}{'...' if len(cmd)>120 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        for line in out.strip().split('\n')[:50]:
            print(f"  {line}")
        if len(out.strip().split('\n')) > 50:
            print(f"  ... ({len(out.strip().split(chr(10)))} lines total)")
    if err.strip() and exit_code != 0:
        for line in err.strip().split('\n')[:30]:
            print(f"  ERR: {line}")
    return out, err, exit_code

def upload_file(ssh, local_path, remote_path):
    sftp = ssh.open_sftp()
    size_mb = os.path.getsize(local_path) / (1024*1024)
    print(f"[UPLOAD] {local_path} -> {remote_path} ({size_mb:.1f} MB)")
    start = time.time()
    sftp.put(local_path, remote_path)
    elapsed = time.time() - start
    print(f"[UPLOAD] Done in {elapsed:.1f}s")
    sftp.close()

def main():
    tar_path = create_tar()

    ssh = get_ssh()
    print(f"\n[SSH] Connected to {SERVER}")

    run_cmd(ssh, f'mkdir -p {REMOTE_DIR}')

    upload_file(ssh, tar_path, f'{REMOTE_DIR}/deploy_package.tar.gz')

    print("\n[DEPLOY] Extracting files...")
    run_cmd(ssh, f'cd {REMOTE_DIR} && tar xzf deploy_package.tar.gz')

    print("\n[DEPLOY] Stopping old containers...")
    run_cmd(ssh, f'cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down 2>/dev/null || true', timeout=120)

    print("\n[DEPLOY] Building containers (this may take several minutes)...")
    out, err, code = run_cmd(ssh, f'cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1', timeout=600)
    if code != 0:
        print(f"\n[ERROR] Build failed with exit code {code}")
        print("Full build output:")
        print(out)
        print(err)
        ssh.close()
        sys.exit(1)

    print("\n[DEPLOY] Starting containers...")
    out, err, code = run_cmd(ssh, f'cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1', timeout=120)
    if code != 0:
        print(f"\n[ERROR] Start failed with exit code {code}")
        print(err)
        ssh.close()
        sys.exit(1)

    print("\n[DEPLOY] Waiting 30s for containers to start...")
    time.sleep(30)

    print("\n[CHECK] Container status:")
    run_cmd(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")

    print("\n[CHECK] Checking gateway network connectivity...")
    run_cmd(ssh, f'docker network inspect {DEPLOY_ID}-network --format "{{{{.Containers}}}}" 2>/dev/null | tr "," "\\n" || echo "Network not found"')

    gateway_connected = False
    out, _, _ = run_cmd(ssh, f'docker network inspect {DEPLOY_ID}-network --format "{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}" 2>/dev/null')
    if 'gateway' in out.lower():
        gateway_connected = True
        print("  Gateway is connected to project network")
    else:
        print("  Gateway not connected, connecting now...")
        run_cmd(ssh, f'docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true')
        time.sleep(2)
        out2, _, _ = run_cmd(ssh, f'docker network inspect {DEPLOY_ID}-network --format "{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}" 2>/dev/null')
        if 'gateway' in out2.lower():
            gateway_connected = True
            print("  Gateway connected successfully")
        else:
            print("  WARN: Could not connect gateway")

    print("\n[GATEWAY] Checking/updating gateway route config...")
    out, _, _ = run_cmd(ssh, 'docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null || echo "NO_GATEWAY"')
    if 'NO_GATEWAY' not in out:
        run_cmd(ssh, f'docker cp {REMOTE_DIR}/gateway-routes.conf gateway-nginx:/etc/nginx/conf.d/{DEPLOY_ID}.conf')
        run_cmd(ssh, 'docker exec gateway-nginx nginx -t 2>&1')
        run_cmd(ssh, 'docker exec gateway-nginx nginx -s reload 2>&1')
        print("  Gateway routes updated and reloaded")

    print("\n[VERIFY] Health checks:")
    base_url = f'https://newbb.bangbangvip.com/autodev/{DEPLOY_ID}'

    out, _, code = run_cmd(ssh, f'curl -s {base_url}/api/health 2>/dev/null || echo "FAILED"')
    api_ok = code == 0 and 'FAILED' not in out and ('healthy' in out.lower() or 'ok' in out.lower() or '{' in out)
    print(f"  API Health: {'OK' if api_ok else 'FAILED'}")

    out, _, code = run_cmd(ssh, f'curl -Is {base_url}/admin/ 2>/dev/null | head -5')
    admin_ok = '200' in out or '304' in out or '301' in out or '302' in out
    print(f"  Admin Web: {'OK' if admin_ok else 'FAILED'}")

    out, _, code = run_cmd(ssh, f'curl -Is {base_url}/ 2>/dev/null | head -5')
    h5_ok = '200' in out or '304' in out or '301' in out or '302' in out
    print(f"  H5 Web: {'OK' if h5_ok else 'FAILED'}")

    print("\n" + "="*60)
    all_ok = api_ok and admin_ok and h5_ok
    if all_ok:
        print("DEPLOY_SUCCESS")
        print(f"  API:   {base_url}/api/health")
        print(f"  Admin: {base_url}/admin/")
        print(f"  H5:    {base_url}/")
    else:
        print("DEPLOY_PARTIAL")
        if not api_ok:
            print("  WARN: API health check failed")
            run_cmd(ssh, f'docker logs {DEPLOY_ID}-backend --tail 30 2>&1')
        if not admin_ok:
            print("  WARN: Admin frontend not responding")
            run_cmd(ssh, f'docker logs {DEPLOY_ID}-admin --tail 30 2>&1')
        if not h5_ok:
            print("  WARN: H5 frontend not responding")
            run_cmd(ssh, f'docker logs {DEPLOY_ID}-h5 --tail 30 2>&1')
    print("="*60)

    ssh.close()
    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    main()
