import paramiko
import os
import sys
import tarfile
import time

SERVER = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'

INCLUDE_ITEMS = [
    'backend',
    'h5-web',
    'admin-web',
    'docker-compose.prod.yml',
    'deploy',
]

EXCLUDE_DIRS = {
    'node_modules', '.next', '__pycache__', '.mypy_cache',
    '.pytest_cache', 'dist', '.git', 'venv', '.venv',
}

def should_exclude(tarinfo):
    parts = tarinfo.name.replace('\\', '/').split('/')
    for part in parts:
        if part in EXCLUDE_DIRS:
            return None
    if tarinfo.name.endswith(('.pyc', '.DS_Store', 'Thumbs.db', '.tar.gz')):
        return None
    return tarinfo

def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tar_path = os.path.join(project_dir, 'deploy', 'project_slim.tar.gz')

    print("Creating slim tar archive...")
    with tarfile.open(tar_path, 'w:gz', compresslevel=6) as tar:
        for item in INCLUDE_ITEMS:
            full_path = os.path.join(project_dir, item)
            if os.path.exists(full_path):
                tar.add(full_path, arcname=item, filter=should_exclude)
                print(f"  Added: {item}")
            else:
                print(f"  SKIP (not found): {item}")

    tar_size = os.path.getsize(tar_path) / (1024*1024)
    print(f"Archive created: {tar_size:.1f} MB")

    print("\nConnecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)

    stdin, stdout, stderr = ssh.exec_command(f'mkdir -p {REMOTE_DIR}')
    stdout.channel.recv_exit_status()

    print("Uploading archive...")
    sftp = ssh.open_sftp()
    remote_tar = f'{REMOTE_DIR}/project_slim.tar.gz'
    
    start = time.time()
    sftp.put(tar_path, remote_tar)
    elapsed = time.time() - start
    speed = tar_size / elapsed if elapsed > 0 else 0
    print(f"Upload complete in {elapsed:.0f}s ({speed:.1f} MB/s)")
    sftp.close()

    print("Extracting on server...")
    stdin, stdout, stderr = ssh.exec_command(
        f'cd {REMOTE_DIR} && tar xzf project_slim.tar.gz && rm project_slim.tar.gz && echo EXTRACT_OK',
        timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    print(out.strip())
    if code != 0:
        print(f"Extract error: {err}")
        sys.exit(1)

    os.remove(tar_path)
    print("Local tar cleaned up.")
    
    ssh.close()
    print("Upload complete!")

if __name__ == '__main__':
    main()
