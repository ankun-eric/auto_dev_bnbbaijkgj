#!/usr/bin/env python3
"""Deploy bini-health project to remote server via SSH/SFTP."""
import paramiko
import os
import sys
import stat
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
LOCAL_ROOT = r'C:\auto_output\bnbbaijkgj'

EXCLUDE_DIRS = {
    'node_modules', '.git', '__pycache__', '.next', '.pytest_cache',
    '.cursor', '.chat_attachments', '.chat_output', 'deploy', 'mem',
    'docs', 'user_docs', 'static', 'tests', 'flutter_app', 'miniprogram',
    '.github', '_deploy_tmp', '.tools',
}
EXCLUDE_EXTENSIONS = {'.apk', '.zip', '.tar.gz', '.tar', '.png', '.docx'}
EXCLUDE_FILES = {
    '.dev_start_commit.txt', '.changed_files.txt', '.deploy.sh',
    'project-context.mdc', 'tsconfig.tsbuildinfo',
}

SYNC_DIRS = ['backend', 'h5-web', 'admin-web']

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out[:5000])
    if err:
        err_clean = err.strip()
        if err_clean:
            print(f"STDERR: {err_clean[:3000]}")
    print(f"[exit_code: {exit_code}]")
    return out, err, exit_code

def should_exclude(name, is_dir=False):
    if is_dir and name in EXCLUDE_DIRS:
        return True
    if not is_dir:
        if name in EXCLUDE_FILES:
            return True
        for ext in EXCLUDE_EXTENSIONS:
            if name.endswith(ext):
                return True
    return False

def sftp_mkdir_p(sftp, remote_path):
    dirs_to_create = []
    current = remote_path
    while True:
        try:
            sftp.stat(current)
            break
        except FileNotFoundError:
            dirs_to_create.append(current)
            current = os.path.dirname(current)
            if current == '/' or current == '':
                break
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except Exception:
            pass

def sync_directory(sftp, local_dir, remote_dir, sync_dirs_only=None):
    count = 0
    for root, dirs, files in os.walk(local_dir):
        rel_root = os.path.relpath(root, local_dir).replace('\\', '/')
        if rel_root == '.':
            rel_root = ''

        if sync_dirs_only and rel_root == '':
            dirs[:] = [d for d in dirs if d in sync_dirs_only and not should_exclude(d, True)]
        else:
            dirs[:] = [d for d in dirs if not should_exclude(d, True)]

        for filename in files:
            if should_exclude(filename, False):
                continue

            local_path = os.path.join(root, filename)
            if rel_root:
                remote_path = f"{remote_dir}/{rel_root}/{filename}"
            else:
                remote_path = f"{remote_dir}/{filename}"

            remote_parent = os.path.dirname(remote_path).replace('\\', '/')
            sftp_mkdir_p(sftp, remote_parent)

            try:
                sftp.put(local_path, remote_path)
                count += 1
                if count % 20 == 0:
                    print(f"  ... synced {count} files")
            except Exception as e:
                print(f"  WARN: failed to upload {remote_path}: {e}")

    return count

def sync_root_files(sftp, local_dir, remote_dir):
    count = 0
    root_files = ['docker-compose.yml', '.dockerignore', '.env']
    for fname in root_files:
        local_path = os.path.join(local_dir, fname)
        if os.path.exists(local_path):
            remote_path = f"{remote_dir}/{fname}"
            try:
                sftp.put(local_path, remote_path)
                count += 1
                print(f"  Synced root file: {fname}")
            except Exception as e:
                print(f"  WARN: failed {fname}: {e}")
    return count

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'full'

    ssh = get_ssh()

    if action in ('full', 'sync'):
        print("=" * 60)
        print("STEP 1: Syncing code to server via SFTP")
        print("=" * 60)

        sftp = ssh.open_sftp()

        total = sync_root_files(sftp, LOCAL_ROOT, PROJECT_DIR)
        print(f"\nSyncing directories: {SYNC_DIRS}")
        total += sync_directory(sftp, LOCAL_ROOT, PROJECT_DIR, sync_dirs_only=set(SYNC_DIRS))
        sftp.close()
        print(f"\nTotal files synced: {total}")

    if action in ('full', 'build'):
        print("\n" + "=" * 60)
        print("STEP 2: Rebuilding containers")
        print("=" * 60)

        run_cmd(ssh, f"cd {PROJECT_DIR} && docker compose stop backend admin-web h5-web")
        run_cmd(ssh, f"cd {PROJECT_DIR} && docker compose rm -f backend admin-web h5-web")

        run_cmd(ssh,
            f"cd {PROJECT_DIR} && docker compose build --no-cache backend 2>&1 | tail -30",
            timeout=600)

        run_cmd(ssh,
            f"cd {PROJECT_DIR} && docker compose build --no-cache admin-web 2>&1 | tail -30",
            timeout=600)

        run_cmd(ssh,
            f"cd {PROJECT_DIR} && docker compose build --no-cache h5-web 2>&1 | tail -30",
            timeout=600)

        run_cmd(ssh, f"cd {PROJECT_DIR} && docker compose up -d", timeout=120)

        print("\nWaiting 15s for containers to start...")
        time.sleep(15)

        run_cmd(ssh,
            'docker ps -a --filter name=6b099ed3 --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')

    if action in ('full', 'gateway'):
        print("\n" + "=" * 60)
        print("STEP 3: Checking gateway connectivity")
        print("=" * 60)

        run_cmd(ssh, 'docker network ls --filter name=gateway --format "{{.Name}}"')

        out, _, _ = run_cmd(ssh,
            'docker network inspect gateway-network --format "{{range .Containers}}{{.Name}} {{end}}" 2>/dev/null || echo NO_GATEWAY_NETWORK')

        containers_needed = [
            '6b099ed3-7175-4a78-91f4-44570c84ed27-backend',
            '6b099ed3-7175-4a78-91f4-44570c84ed27-admin',
            '6b099ed3-7175-4a78-91f4-44570c84ed27-h5',
        ]

        for c in containers_needed:
            if c not in out:
                print(f"  Connecting {c} to gateway-network...")
                run_cmd(ssh, f"docker network connect gateway-network {c} 2>/dev/null || true")

        run_cmd(ssh, "docker exec gateway-nginx nginx -s reload 2>/dev/null || true")

    ssh.close()
    print("\n" + "=" * 60)
    print("Deployment script completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
