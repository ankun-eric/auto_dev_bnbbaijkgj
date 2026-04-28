import paramiko
import os
import stat
import sys
from pathlib import Path

EXCLUDES = {
    'node_modules', '.git', '__pycache__', '.next', '.pytest_cache',
    'flutter_app', 'miniprogram', 'verify-miniprogram', 'build_artifacts',
    'dist', 'apk_download', 'uploads', '.tools', '.chat_attachments',
    '.chat_output', '.chat_prompts', '.consulting_output', 'ui_design_outputs',
    'mem', 'docs', 'tests', 'user_docs', '.cursor'
}

EXCLUDE_EXTENSIONS = {'.apk', '.zip'}

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
REMOTE_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/'
LOCAL_DIR = r'C:\auto_output\bnbbaijkgj'


def should_exclude(name, is_dir=False):
    if name in EXCLUDES:
        return True
    if not is_dir:
        _, ext = os.path.splitext(name)
        if ext.lower() in EXCLUDE_EXTENSIONS:
            return True
    return False


def get_all_files(local_dir):
    files = []
    for root, dirs, filenames in os.walk(local_dir):
        dirs[:] = [d for d in dirs if not should_exclude(d, True)]
        for f in filenames:
            if should_exclude(f, False):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, local_dir).replace('\\', '/')
            files.append((full_path, rel_path))
    return files


def ensure_remote_dir(sftp, remote_path):
    dirs_to_create = []
    path = remote_path
    while path and path != '/':
        try:
            sftp.stat(path)
            break
        except FileNotFoundError:
            dirs_to_create.append(path)
            path = os.path.dirname(path)
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except Exception:
            pass


def main():
    print(f"Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    
    sftp = ssh.open_sftp()
    
    files = get_all_files(LOCAL_DIR)
    print(f"Found {len(files)} files to sync")
    
    uploaded = 0
    errors = 0
    for full_path, rel_path in files:
        remote_path = REMOTE_DIR + rel_path
        remote_dir = os.path.dirname(remote_path).replace('\\', '/')
        try:
            ensure_remote_dir(sftp, remote_dir)
            sftp.put(full_path, remote_path)
            uploaded += 1
            if uploaded % 50 == 0:
                print(f"  Uploaded {uploaded}/{len(files)} files...")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error uploading {rel_path}: {e}")
    
    print(f"\nSync complete: {uploaded} uploaded, {errors} errors")
    sftp.close()
    ssh.close()


if __name__ == '__main__':
    main()
