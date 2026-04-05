"""Transfer project files to remote server using paramiko SFTP with chunked upload."""
import paramiko
import os
import sys
import time

SERVER = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Bangbang987'
DEPLOY_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_DIR = r'C:\auto_output\bnbbaijkgj'

EXCLUDES = {
    'node_modules', '.git', '__pycache__', '.next', '.env',
    'deploy_helper.py', 'deploy_transfer.py', 'project.tar.gz',
    'tsconfig.tsbuildinfo', '.cursor', '.github', '.pytest_cache',
    'ui_design_outputs',
}

EXCLUDE_EXTS = {'.pyc', '.apk', '.zip', '.png', '.docx'}

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    transport = ssh.get_transport()
    transport.set_keepalive(15)
    return ssh

def run_cmd(ssh, cmd, timeout=300):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def create_tar():
    import tarfile
    tar_path = os.path.join(LOCAL_DIR, 'project.tar.gz')
    print("Creating tar archive...")
    with tarfile.open(tar_path, 'w:gz', compresslevel=6) as tar:
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
    size_mb = os.path.getsize(tar_path) / (1024*1024)
    print(f"Archive created: {size_mb:.1f} MB")
    return tar_path

def chunked_upload(sftp, local_path, remote_path, chunk_size=1024*1024):
    """Upload file in chunks for reliability."""
    file_size = os.path.getsize(local_path)
    uploaded = 0
    last_print = time.time()
    
    with open(local_path, 'rb') as local_f:
        with sftp.open(remote_path, 'wb') as remote_f:
            remote_f.set_pipelined(True)
            while True:
                data = local_f.read(chunk_size)
                if not data:
                    break
                remote_f.write(data)
                uploaded += len(data)
                now = time.time()
                if now - last_print > 5:
                    pct = (uploaded / file_size) * 100
                    print(f"  Upload: {pct:.0f}% ({uploaded/1024/1024:.1f}/{file_size/1024/1024:.1f} MB)")
                    last_print = now
    
    print(f"  Upload: 100% ({file_size/1024/1024:.1f} MB)")
    remote_stat = sftp.stat(remote_path)
    if remote_stat.st_size != file_size:
        raise Exception(f"Size mismatch: local={file_size}, remote={remote_stat.st_size}")
    print(f"  Verified: remote size matches ({remote_stat.st_size} bytes)")

def upload_and_extract():
    tar_path = create_tar()
    
    ssh = get_ssh()
    print("Connected to server")
    
    run_cmd(ssh, f'mkdir -p {REMOTE_DIR}')
    
    sftp = ssh.open_sftp()
    sftp.get_channel().settimeout(300)
    remote_tar = f'{REMOTE_DIR}/project.tar.gz'
    
    print(f"Uploading to {remote_tar}...")
    chunked_upload(sftp, tar_path, remote_tar)
    sftp.close()
    print("Upload complete")
    
    print("Extracting on server...")
    out, err, code = run_cmd(ssh, f'cd {REMOTE_DIR} && tar xzf project.tar.gz && rm project.tar.gz && echo EXTRACT_OK')
    if 'EXTRACT_OK' not in out:
        print(f"Extract error: {err} {out}")
        sys.exit(1)
    print("Extract complete")
    
    out, _, _ = run_cmd(ssh, f'ls -la {REMOTE_DIR}/')
    print(out)
    
    ssh.close()
    os.remove(tar_path)
    print("Transfer done")

if __name__ == '__main__':
    upload_and_extract()
