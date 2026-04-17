import paramiko
import os
import stat
import sys
import time

HOSTNAME = "newbb.test.bangbangvip.com"
USERNAME = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", ".next", "__pycache__", ".git", ".venv", "venv",
    ".cursor", ".github", ".tools", ".chat_output", ".consulting_output",
    "build_artifacts", "deploy", "docs", "mem", "tests", "uploads",
    "ui_design_outputs", "user_docs", "verify-miniprogram", "apk_download",
    "dist", ".nuxt", ".output", "coverage", ".pytest_cache", ".mypy_cache",
}

EXCLUDE_EXTENSIONS = {
    ".apk", ".zip", ".tar", ".tar.gz", ".png", ".jpg", ".jpeg", ".gif",
    ".exe", ".msi", ".dmg",
}

SYNC_DIRS = ["backend", "h5-web", "admin-web"]
SYNC_FILES = ["docker-compose.yml"]

def should_exclude(path, name):
    if name in EXCLUDE_DIRS:
        return True
    _, ext = os.path.splitext(name)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return True
    return False

def ensure_remote_dir(sftp, remote_path):
    dirs_to_create = []
    current = remote_path
    while True:
        try:
            sftp.stat(current)
            break
        except FileNotFoundError:
            dirs_to_create.append(current)
            current = os.path.dirname(current).replace("\\", "/")
            if current == "/" or current == "":
                break
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except:
            pass

def sync_directory(sftp, local_path, remote_path, file_count=0):
    ensure_remote_dir(sftp, remote_path)
    for item in os.listdir(local_path):
        if should_exclude(local_path, item):
            continue
        local_item = os.path.join(local_path, item)
        remote_item = remote_path + "/" + item
        if os.path.isdir(local_item):
            file_count = sync_directory(sftp, local_item, remote_item, file_count)
        elif os.path.isfile(local_item):
            try:
                sftp.put(local_item, remote_item)
                file_count += 1
                if file_count % 50 == 0:
                    print(f"  Uploaded {file_count} files...")
            except Exception as e:
                print(f"  Error uploading {remote_item}: {e}")
    return file_count

def main():
    print("Connecting to server...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    total_files = 0
    for sync_dir in SYNC_DIRS:
        local_path = os.path.join(LOCAL_DIR, sync_dir)
        remote_path = f"{REMOTE_DIR}/{sync_dir}"
        if os.path.exists(local_path):
            print(f"\nSyncing {sync_dir}...")
            count = sync_directory(sftp, local_path, remote_path)
            total_files += count
            print(f"  {sync_dir}: {count} files uploaded")
        else:
            print(f"  Skipping {sync_dir} (not found locally)")

    for sync_file in SYNC_FILES:
        local_file = os.path.join(LOCAL_DIR, sync_file)
        remote_file = f"{REMOTE_DIR}/{sync_file}"
        if os.path.exists(local_file):
            print(f"\nSyncing {sync_file}...")
            sftp.put(local_file, remote_file)
            total_files += 1
            print(f"  {sync_file}: uploaded")

    sftp.close()
    client.close()
    print(f"\nSync complete! Total files uploaded: {total_files}")

if __name__ == "__main__":
    main()
