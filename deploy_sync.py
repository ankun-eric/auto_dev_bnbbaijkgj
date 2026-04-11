import paramiko
import os
import stat
import sys
import time

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
REMOTE_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", ".git", ".next", "__pycache__", ".venv",
    ".pytest_cache", ".dart_tool", "build", ".packages",
    ".cursor", "terminals", "agent-transcripts",
}
EXCLUDE_EXTENSIONS = {".pyc", ".apk", ".zip", ".tar.gz", ".tar"}
EXCLUDE_FILES = {"deploy_sync.py"}

def should_exclude(rel_path):
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    _, ext = os.path.splitext(rel_path)
    if ext in EXCLUDE_EXTENSIONS:
        return True
    basename = os.path.basename(rel_path)
    if basename in EXCLUDE_FILES:
        return True
    return False

def upload_directory(sftp, local_dir, remote_dir):
    file_count = 0
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        rel_root = os.path.relpath(root, local_dir)
        if rel_root == ".":
            remote_root = remote_dir
        else:
            remote_root = remote_dir + "/" + rel_root.replace("\\", "/")
        
        if should_exclude(rel_root) and rel_root != ".":
            continue
        
        try:
            sftp.stat(remote_root)
        except FileNotFoundError:
            try:
                sftp.mkdir(remote_root)
                print(f"  Created dir: {remote_root}")
            except Exception:
                parts = remote_root.split("/")
                for i in range(1, len(parts) + 1):
                    partial = "/".join(parts[:i])
                    if not partial:
                        continue
                    try:
                        sftp.stat(partial)
                    except FileNotFoundError:
                        sftp.mkdir(partial)
        
        for f in files:
            local_path = os.path.join(root, f)
            rel_path = os.path.relpath(local_path, local_dir)
            
            if should_exclude(rel_path):
                continue
            
            remote_path = remote_root + "/" + f
            
            try:
                local_stat = os.stat(local_path)
                local_mtime = local_stat.st_mtime
                local_size = local_stat.st_size
                
                try:
                    remote_stat = sftp.stat(remote_path)
                    if remote_stat.st_size == local_size and abs(remote_stat.st_mtime - local_mtime) < 2:
                        continue
                except FileNotFoundError:
                    pass
                
                sftp.put(local_path, remote_path)
                file_count += 1
                if file_count % 50 == 0:
                    print(f"  Uploaded {file_count} files...")
            except Exception as e:
                print(f"  Error uploading {rel_path}: {e}")
    
    return file_count

def main():
    print(f"Connecting to {SERVER}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    print("Connected!")
    
    sftp = ssh.open_sftp()
    
    try:
        sftp.stat(REMOTE_DIR)
    except FileNotFoundError:
        sftp.mkdir(REMOTE_DIR)
        print(f"Created remote directory: {REMOTE_DIR}")
    
    print(f"Syncing files from {LOCAL_DIR} to {REMOTE_DIR}...")
    count = upload_directory(sftp, LOCAL_DIR, REMOTE_DIR.rstrip("/"))
    print(f"Sync complete! Uploaded {count} files.")
    
    sftp.close()
    ssh.close()

if __name__ == "__main__":
    main()
