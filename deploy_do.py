"""Reliable project transfer with chunked upload and verification."""
import paramiko
import os
import sys
import time
import tarfile
import hashlib

SERVER = 'newbb.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_DIR = r'C:\auto_output\bnbbaijkgj'

EXCLUDES = {
    'node_modules', '.git', '__pycache__', '.next', '.env', '.pytest_cache',
    'deploy_helper.py', 'deploy_transfer.py', 'deploy_now.py', 'deploy_remote.py',
    'deploy_upload.py', 'deploy_do.py', 'deploy_port_check.py', 'deploy_ssh.py',
    'do_deploy.py', 'project.tar.gz', 'deploy_package.tar.gz', 'deploy_upload.tar.gz',
    'tsconfig.tsbuildinfo', '.cursor', 'agent-transcripts',
}
EXCLUDE_EXTS = {'.pyc', '.apk', '.zip'}

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, timeout=600):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def create_tar():
    tar_path = os.path.join(LOCAL_DIR, 'project.tar.gz')
    if os.path.exists(tar_path):
        os.remove(tar_path)
    print("Creating tar archive...")
    with tarfile.open(tar_path, 'w:gz') as tar:
        for root, dirs, files in os.walk(LOCAL_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDES]
            for f in files:
                if f in EXCLUDES:
                    continue
                if any(f.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, LOCAL_DIR)
                try:
                    tar.add(full, arcname=arcname)
                except Exception as e:
                    print(f"  Skip {arcname}: {e}")
    size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"Archive created: {size_mb:.1f} MB")
    return tar_path

def upload_chunked(ssh, local_path, remote_path, chunk_size=1024*1024):
    """Upload file using raw SFTP write for reliability."""
    sftp = ssh.open_sftp()
    local_size = os.path.getsize(local_path)
    uploaded = 0
    last_report = time.time()

    with open(local_path, 'rb') as lf:
        with sftp.file(remote_path, 'wb') as rf:
            rf.set_pipelined(True)
            while True:
                data = lf.read(chunk_size)
                if not data:
                    break
                rf.write(data)
                uploaded += len(data)
                now = time.time()
                if now - last_report > 5:
                    pct = (uploaded / local_size) * 100
                    print(f"  Upload: {pct:.0f}% ({uploaded // (1024*1024)}/{local_size // (1024*1024)} MB)")
                    last_report = now

    print(f"  Upload: 100% ({local_size // (1024*1024)} MB)")

    stat = sftp.stat(remote_path)
    sftp.close()

    if stat.st_size != local_size:
        raise Exception(f"Size mismatch: local={local_size} remote={stat.st_size}")
    print(f"Upload verified: {stat.st_size} bytes")

def main():
    tar_path = create_tar()
    local_md5 = md5_file(tar_path)
    local_size = os.path.getsize(tar_path)
    print(f"Local MD5: {local_md5}, Size: {local_size}")

    ssh = get_ssh()
    print("Connected to server")

    run_cmd(ssh, f'mkdir -p {REMOTE_DIR}')

    remote_tar = f'{REMOTE_DIR}/project.tar.gz'
    print(f"Uploading to {remote_tar}...")
    upload_chunked(ssh, tar_path, remote_tar)

    print("Verifying remote MD5...")
    out, err, code = run_cmd(ssh, f'md5sum {remote_tar}')
    remote_md5 = out.split()[0] if out else ''
    print(f"Remote MD5: {remote_md5}")
    if remote_md5 != local_md5:
        print(f"MD5 MISMATCH! local={local_md5} remote={remote_md5}")
        sys.exit(1)
    print("MD5 verified OK")

    print("Extracting on server...")
    out, err, code = run_cmd(ssh, f'cd {REMOTE_DIR} && tar xzf project.tar.gz && rm project.tar.gz', timeout=120)
    if code != 0:
        print(f"Extract error: {err}")
        sys.exit(1)
    print("Extract complete")

    out, _, _ = run_cmd(ssh, f'ls -la {REMOTE_DIR}/')
    print(out)

    ssh.close()
    os.remove(tar_path)
    print("TRANSFER_SUCCESS")

if __name__ == '__main__':
    main()
