import paramiko
import os
import sys
import stat
import time

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", ".next", "__pycache__", ".git", "venv", ".venv",
    "flutter_app", "miniprogram", "_deploy_tmp", ".cursor"
}

EXCLUDE_FILES = {".env.local"}

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh

def ssh_exec(ssh, cmd, timeout=300):
    print(f"  [SSH] {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  [OUT] {out[:500]}")
    if err.strip():
        print(f"  [ERR] {err[:500]}")
    return rc, out, err

def sync_files():
    print("=== Syncing files via SFTP ===")
    ssh = get_ssh()
    sftp = ssh.open_sftp()

    def ensure_remote_dir(path):
        try:
            sftp.stat(path)
        except FileNotFoundError:
            ensure_remote_dir(os.path.dirname(path))
            sftp.mkdir(path)

    ensure_remote_dir(REMOTE_DIR)

    file_count = 0
    for root, dirs, files in os.walk(LOCAL_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        rel_root = os.path.relpath(root, LOCAL_DIR).replace("\\", "/")
        if rel_root == ".":
            rel_root = ""
        
        remote_root = f"{REMOTE_DIR}/{rel_root}" if rel_root else REMOTE_DIR
        ensure_remote_dir(remote_root)
        
        for f in files:
            if f in EXCLUDE_FILES:
                continue
            local_path = os.path.join(root, f)
            rel_path = f"{rel_root}/{f}" if rel_root else f
            remote_path = f"{REMOTE_DIR}/{rel_path}"
            
            try:
                local_mtime = os.path.getmtime(local_path)
                local_size = os.path.getsize(local_path)
                
                need_upload = True
                try:
                    remote_stat = sftp.stat(remote_path)
                    if remote_stat.st_size == local_size and remote_stat.st_mtime >= local_mtime - 2:
                        need_upload = False
                except:
                    pass
                
                if need_upload:
                    sftp.put(local_path, remote_path)
                    file_count += 1
                    if file_count % 50 == 0:
                        print(f"  Uploaded {file_count} files...")
            except Exception as e:
                print(f"  WARN: Failed to upload {rel_path}: {e}")
    
    print(f"  Total files uploaded/updated: {file_count}")
    sftp.close()
    ssh.close()

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    
    if action == "sync":
        sync_files()
        print("=== Sync complete ===")
    
    elif action == "build":
        ssh = get_ssh()
        print("=== Building Docker containers (this may take several minutes) ===")
        cmd = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1"
        rc, out, err = ssh_exec(ssh, cmd, timeout=600)
        if rc != 0:
            print(f"BUILD FAILED (exit code {rc})")
            sys.exit(1)
        print("=== Build complete, starting containers ===")
        cmd = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1"
        rc, out, err = ssh_exec(ssh, cmd, timeout=120)
        if rc != 0:
            print(f"UP FAILED (exit code {rc})")
            sys.exit(1)
        print("=== Containers started ===")
        ssh.close()
    
    elif action == "status":
        ssh = get_ssh()
        rc, out, err = ssh_exec(ssh, "docker ps --filter 'name=6b099ed3' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
        print(out)
        ssh.close()
    
    elif action == "exec":
        ssh = get_ssh()
        cmd = " ".join(sys.argv[2:])
        rc, out, err = ssh_exec(ssh, cmd, timeout=120)
        sys.exit(rc)
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
