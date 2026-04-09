"""Deploy script: sync files to remote server and rebuild containers."""
import os
import sys
import stat
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"
REMOTE_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

EXCLUDE_DIRS = {
    "node_modules", "__pycache__", ".git", ".next", ".venv",
    "build", ".dart_tool", ".flutter-plugins-dependencies",
    ".idea", ".cursor", ".chat_output", "_deploy_tmp",
    "deploy_package.tar.gz", ".gradle", "android", "ios",
    "macos", "linux", "windows", "web",
}
EXCLUDE_EXTS = {".pyc", ".pyo"}


def should_exclude(name, is_dir=False):
    if name in EXCLUDE_DIRS:
        return True
    if not is_dir:
        _, ext = os.path.splitext(name)
        if ext in EXCLUDE_EXTS:
            return True
    return False


def sftp_upload_dir(sftp, local_path, remote_path, depth=0):
    prefix = "  " * depth
    try:
        sftp.stat(remote_path)
    except FileNotFoundError:
        sftp.mkdir(remote_path)

    items = os.listdir(local_path)
    for item in items:
        local_item = os.path.join(local_path, item)
        remote_item = remote_path + "/" + item
        is_dir = os.path.isdir(local_item)

        if should_exclude(item, is_dir):
            continue

        if is_dir:
            print(f"{prefix}[DIR] {item}/")
            sftp_upload_dir(sftp, local_item, remote_item, depth + 1)
        else:
            size = os.path.getsize(local_item)
            if size > 50 * 1024 * 1024:
                print(f"{prefix}[SKIP] {item} (too large: {size // 1024 // 1024}MB)")
                continue
            try:
                remote_stat = sftp.stat(remote_item)
                local_mtime = os.path.getmtime(local_item)
                if abs(remote_stat.st_mtime - local_mtime) < 1 and remote_stat.st_size == size:
                    continue
            except FileNotFoundError:
                pass
            print(f"{prefix}[FILE] {item} ({size // 1024}KB)")
            sftp.put(local_item, remote_item)


def run_remote(ssh, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print(f"[STDERR] {err}")
    print(f"[EXIT CODE] {exit_code}")
    return exit_code, out, err


def main():
    print("=" * 60)
    print("Connecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected!")

    print("\n" + "=" * 60)
    print("Uploading files to server...")
    sftp = ssh.open_sftp()
    sftp_upload_dir(sftp, LOCAL_DIR, REMOTE_DIR)
    sftp.close()
    print("Upload complete!")

    print("\n" + "=" * 60)
    print("Building and restarting containers...")

    cd = f"cd {REMOTE_DIR}"

    run_remote(ssh, f"{cd} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web", timeout=600)
    run_remote(ssh, f"{cd} && docker compose -f docker-compose.prod.yml up -d backend h5-web", timeout=120)

    print("\nWaiting 15 seconds for containers to start...")
    time.sleep(15)

    run_remote(ssh, f"{cd} && docker compose -f docker-compose.prod.yml ps")

    ssh.close()
    print("\nDeploy script finished!")


if __name__ == "__main__":
    main()
