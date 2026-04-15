import paramiko
import os
import sys
import tarfile
import time

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

INCLUDE_DIRS = {"backend", "admin-web", "h5-web", "deploy", "uploads"}
INCLUDE_ROOT_FILES = {"docker-compose.prod.yml", ".env"}

EXCLUDE_SUBDIRS = {
    "node_modules", ".next", "__pycache__", ".git", "venv", ".venv",
    ".pytest_cache", ".cursor"
}

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh

def ssh_exec(ssh, cmd, timeout=600):
    print(f"  [SSH] {cmd[:200]}")
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    
    stdout_data = []
    stderr_data = []
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65536).decode("utf-8", errors="replace")
            stdout_data.append(chunk)
            sys.stdout.write(chunk)
            sys.stdout.flush()
        if chan.recv_stderr_ready():
            chunk = chan.recv_stderr(65536).decode("utf-8", errors="replace")
            stderr_data.append(chunk)
            sys.stderr.write(chunk)
            sys.stderr.flush()
        if chan.exit_status_ready():
            while chan.recv_ready():
                chunk = chan.recv(65536).decode("utf-8", errors="replace")
                stdout_data.append(chunk)
                sys.stdout.write(chunk)
            while chan.recv_stderr_ready():
                chunk = chan.recv_stderr(65536).decode("utf-8", errors="replace")
                stderr_data.append(chunk)
                sys.stderr.write(chunk)
            break
        time.sleep(0.1)
    
    rc = chan.recv_exit_status()
    return rc, "".join(stdout_data), "".join(stderr_data)

def create_tar():
    print("=== Creating tar archive (source only) ===")
    tar_path = os.path.join(LOCAL_DIR, "_deploy_tmp", "project.tar.gz")
    
    with tarfile.open(tar_path, "w:gz", compresslevel=1) as tar:
        file_count = 0
        
        for fname in os.listdir(LOCAL_DIR):
            fpath = os.path.join(LOCAL_DIR, fname)
            if os.path.isfile(fpath) and fname in INCLUDE_ROOT_FILES:
                tar.add(fpath, arcname=fname)
                file_count += 1
        
        for dirname in INCLUDE_DIRS:
            dirpath = os.path.join(LOCAL_DIR, dirname)
            if not os.path.isdir(dirpath):
                continue
            for root, dirs, files in os.walk(dirpath):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_SUBDIRS]
                for f in files:
                    local_path = os.path.join(root, f)
                    arcname = os.path.relpath(local_path, LOCAL_DIR).replace("\\", "/")
                    try:
                        tar.add(local_path, arcname=arcname)
                        file_count += 1
                    except Exception as e:
                        pass
        
        print(f"  Archived {file_count} files")
    
    size_mb = os.path.getsize(tar_path) / (1024*1024)
    print(f"  Archive size: {size_mb:.1f} MB")
    return tar_path

def upload_tar(tar_path):
    print("=== Uploading archive to server ===")
    ssh = get_ssh()
    sftp = ssh.open_sftp()
    
    ssh_exec(ssh, f"mkdir -p {REMOTE_DIR}")
    
    remote_tar = f"{REMOTE_DIR}/project.tar.gz"
    total_size = os.path.getsize(tar_path)
    start = time.time()
    last_print = [0]
    
    def progress(sent, total):
        now = time.time()
        if now - last_print[0] > 5:
            pct = sent * 100 / total
            elapsed = now - start
            speed = sent / (1024*1024) / max(elapsed, 0.1)
            print(f"  Upload: {pct:.0f}% ({sent/1024/1024:.1f}/{total/1024/1024:.1f} MB, {speed:.1f} MB/s)")
            last_print[0] = now
    
    sftp.put(tar_path, remote_tar, callback=progress)
    elapsed = time.time() - start
    print(f"  Upload completed in {elapsed:.1f}s")
    sftp.close()
    
    print("=== Extracting archive on server ===")
    rc, out, err = ssh_exec(ssh, f"cd {REMOTE_DIR} && tar xzf project.tar.gz && rm project.tar.gz")
    if rc != 0:
        print(f"Extract failed!")
        sys.exit(1)
    print("  Extract complete")
    ssh.close()

def build():
    ssh = get_ssh()
    print("=== Building Docker containers (may take several minutes) ===")
    rc, out, err = ssh_exec(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    if rc != 0:
        print(f"\nBUILD FAILED (exit code {rc})")
        ssh.close()
        sys.exit(1)
    print("\n=== Starting containers ===")
    rc, out, err = ssh_exec(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    if rc != 0:
        print(f"\nUP FAILED (exit code {rc})")
        ssh.close()
        sys.exit(1)
    print("\n=== Containers started ===")
    ssh.close()

def status():
    ssh = get_ssh()
    rc, out, err = ssh_exec(ssh, "docker ps --filter 'name=6b099ed3' --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'")
    ssh.close()

def remote_exec(cmd):
    ssh = get_ssh()
    rc, out, err = ssh_exec(ssh, cmd, timeout=300)
    ssh.close()
    return rc, out, err

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "full"
    
    if action == "sync":
        tar_path = create_tar()
        upload_tar(tar_path)
        try: os.remove(tar_path)
        except: pass
        print("=== Sync complete ===")
    elif action == "build":
        build()
    elif action == "status":
        status()
    elif action == "exec":
        cmd = " ".join(sys.argv[2:])
        rc, out, err = remote_exec(cmd)
        sys.exit(rc)
    elif action == "full":
        tar_path = create_tar()
        upload_tar(tar_path)
        try: os.remove(tar_path)
        except: pass
        build()
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
