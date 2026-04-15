import paramiko
import os
import stat
import sys
import time

SERVER = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_BASE = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_BASE = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {"node_modules", ".next", "__pycache__", ".git", ".venv", "venv"}
EXCLUDE_EXTS = {".pyc"}
EXCLUDE_FILES = {".env"}

def should_exclude(name, is_dir=False):
    if is_dir and name in EXCLUDE_DIRS:
        return True
    if not is_dir:
        if name in EXCLUDE_FILES:
            return True
        _, ext = os.path.splitext(name)
        if ext in EXCLUDE_EXTS:
            return True
    return False

def sftp_upload_dir(sftp, local_dir, remote_dir):
    count = 0
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)
    
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = remote_dir + "/" + item
        
        if os.path.isdir(local_path):
            if should_exclude(item, is_dir=True):
                continue
            count += sftp_upload_dir(sftp, local_path, remote_path)
        else:
            if should_exclude(item, is_dir=False):
                continue
            try:
                sftp.put(local_path, remote_path)
                count += 1
            except Exception as e:
                print(f"  WARN: Failed to upload {local_path}: {e}")
    return count

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "upload"
    
    print(f"Connecting to {SERVER}:{PORT} as {USER}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("Connected.")
    
    if action == "upload":
        sftp = client.open_sftp()
        
        # Upload backend
        local_backend = os.path.join(LOCAL_BASE, "backend")
        remote_backend = REMOTE_BASE + "/backend"
        print(f"\nUploading backend/ ...")
        n = sftp_upload_dir(sftp, local_backend, remote_backend)
        print(f"  Uploaded {n} files for backend/")
        
        # Upload admin-web
        local_admin = os.path.join(LOCAL_BASE, "admin-web")
        remote_admin = REMOTE_BASE + "/admin-web"
        print(f"\nUploading admin-web/ ...")
        n = sftp_upload_dir(sftp, local_admin, remote_admin)
        print(f"  Uploaded {n} files for admin-web/")
        
        # Upload docker-compose.prod.yml
        local_dc = os.path.join(LOCAL_BASE, "docker-compose.prod.yml")
        remote_dc = REMOTE_BASE + "/docker-compose.prod.yml"
        print(f"\nUploading docker-compose.prod.yml ...")
        sftp.put(local_dc, remote_dc)
        print("  Done.")
        
        sftp.close()
        
    elif action == "exec":
        cmd = sys.argv[2]
        print(f"\nExecuting: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        if out:
            print(out)
        if err:
            print("STDERR:", err)
        print(f"Exit code: {exit_code}")
    
    client.close()

if __name__ == "__main__":
    main()
