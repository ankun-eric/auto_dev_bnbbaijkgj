import paramiko
import os
import tarfile
import io
import sys
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Bangbang987"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"
REMOTE_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".venv", "venv",
    ".cursor", "user_docs", "flutter_app", "miniprogram",
    "verify-miniprogram", ".github"
}
EXCLUDE_EXTS = {".pyc"}
EXCLUDE_FILES = {"deploy_upload.py"}

def should_exclude(path, name):
    if name in EXCLUDE_DIRS or name in EXCLUDE_FILES:
        return True
    _, ext = os.path.splitext(name)
    if ext in EXCLUDE_EXTS:
        return True
    return False

def create_tar():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for root, dirs, files in os.walk(LOCAL_DIR):
            dirs[:] = [d for d in dirs if not should_exclude(root, d)]
            for f in files:
                if should_exclude(root, f):
                    continue
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, LOCAL_DIR).replace("\\", "/")
                try:
                    tar.add(full, arcname=arcname)
                except (PermissionError, OSError) as e:
                    print(f"Skip: {arcname} ({e})")
    buf.seek(0)
    return buf

def main():
    print("Creating archive...")
    tar_buf = create_tar()
    tar_size = tar_buf.getbuffer().nbytes
    print(f"Archive size: {tar_size / 1024 / 1024:.1f} MB")

    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("Connected.")

    print("Uploading archive...")
    sftp = client.open_sftp()
    remote_tar = f"/tmp/deploy_{os.path.basename(LOCAL_DIR)}.tar.gz"
    with sftp.file(remote_tar, 'wb') as rf:
        rf.set_pipelined(True)
        chunk_size = 32768
        total = 0
        while True:
            data = tar_buf.read(chunk_size)
            if not data:
                break
            rf.write(data)
            total += len(data)
            pct = total * 100 // tar_size
            sys.stdout.write(f"\r  {total // 1024}KB / {tar_size // 1024}KB ({pct}%)")
            sys.stdout.flush()
    print("\nUpload done.")
    sftp.close()

    print("Extracting on server...")
    cmds = [
        f"mkdir -p {REMOTE_DIR}",
        f"rm -rf {REMOTE_DIR}/*",
        f"tar xzf {remote_tar} -C {REMOTE_DIR}",
        f"rm -f {remote_tar}",
        f"ls -la {REMOTE_DIR}/ | head -20"
    ]
    for cmd in cmds:
        print(f"  $ {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out)
        if err and 'warning' not in err.lower():
            print(f"  STDERR: {err}")

    client.close()
    print("Upload complete!")

if __name__ == "__main__":
    main()
