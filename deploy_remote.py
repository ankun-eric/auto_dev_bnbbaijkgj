import paramiko
import tarfile
import os
import io
import sys
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
REMOTE_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
LOCAL_DIR = r'C:\auto_output\bnbbaijkgj'

EXCLUDES = {
    'node_modules', '.git', '__pycache__', '.next', '.pytest_cache',
    'flutter_app', 'miniprogram', 'verify-miniprogram', 'build_artifacts',
    'dist', 'apk_download', 'uploads', '.tools', '.chat_attachments',
    '.chat_output', '.chat_prompts', '.consulting_output', 'ui_design_outputs',
    'mem', 'docs', 'tests', 'user_docs', '.cursor', 'deploy_sync.py',
    'deploy_remote.py', 'deploy', '_deploy_tmp', 'agent-transcripts',
    '.venv', 'venv', 'env',
}
EXCLUDE_EXTENSIONS = {'.apk', '.zip'}


def should_exclude(path):
    parts = path.replace('\\', '/').split('/')
    for part in parts:
        if part in EXCLUDES:
            return True
    _, ext = os.path.splitext(path)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return True
    return False


def tar_filter(tarinfo):
    parts = tarinfo.name.split('/')
    for part in parts:
        if part in EXCLUDES:
            return None
    _, ext = os.path.splitext(tarinfo.name)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return None
    return tarinfo


def exec_ssh(ssh, cmd, timeout=600):
    print(f"  $ {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        print(f"    stdout: {out[:500]}")
    if err.strip():
        print(f"    stderr: {err[:500]}")
    print(f"    exit: {exit_code}")
    return exit_code, out, err


def main():
    tar_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'deploy_package.tar.gz')
    
    print("Step 1: Creating tar archive...")
    with tarfile.open(tar_path, 'w:gz') as tar:
        for item in os.listdir(LOCAL_DIR):
            if item in EXCLUDES:
                continue
            full_path = os.path.join(LOCAL_DIR, item)
            tar.add(full_path, arcname=item, filter=tar_filter)
    
    tar_size = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"  Archive created: {tar_size:.1f} MB")
    
    print(f"\nStep 2: Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    
    print("\nStep 3: Uploading archive...")
    sftp = ssh.open_sftp()
    remote_tar = f'/tmp/deploy_package.tar.gz'
    
    start = time.time()
    sftp.put(tar_path, remote_tar, callback=lambda transferred, total: None)
    elapsed = time.time() - start
    print(f"  Upload complete in {elapsed:.1f}s")
    sftp.close()
    
    print("\nStep 4: Extracting on server...")
    exec_ssh(ssh, f'mkdir -p {REMOTE_DIR}')
    exec_ssh(ssh, f'cd {REMOTE_DIR} && tar xzf /tmp/deploy_package.tar.gz --overwrite')
    exec_ssh(ssh, f'rm -f /tmp/deploy_package.tar.gz')
    
    print("\nStep 5: Docker compose down...")
    exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose down', timeout=120)
    
    print("\nStep 6: Docker compose build (this may take a while)...")
    code, out, err = exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose build --no-cache 2>&1', timeout=600)
    if code != 0:
        print("BUILD FAILED! Checking details...")
        exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose build --no-cache 2>&1 | tail -50', timeout=600)
    
    print("\nStep 7: Docker compose up -d...")
    exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose up -d', timeout=120)
    
    print("\nStep 8: Waiting for containers to start (30s)...")
    time.sleep(30)
    
    print("\nStep 9: Checking container status...")
    exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose ps')
    
    print("\nStep 10: Checking backend logs...")
    exec_ssh(ssh, f'cd {REMOTE_DIR} && docker compose logs --tail=30 backend')
    
    print("\nStep 11: Gateway network + nginx reload...")
    exec_ssh(ssh, 'docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>/dev/null; echo "network connected or already connected"')
    exec_ssh(ssh, 'docker exec gateway nginx -t && docker exec gateway nginx -s reload')
    
    print("\nStep 12: Checking gateway config...")
    exec_ssh(ssh, 'cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf')
    
    print("\nStep 13: Link reachability tests...")
    urls = [
        'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/',
        'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/',
        'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs',
    ]
    for url in urls:
        exec_ssh(ssh, f'curl -skI "{url}" | head -5')
    
    ssh.close()
    os.remove(tar_path)
    print("\n=== DEPLOYMENT COMPLETE ===")


if __name__ == '__main__':
    main()
