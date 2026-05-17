"""[PRD-MED-PLAN-OPTIM-V1] 打包小程序为 zip 并上传到服务器"""
import datetime
import os
import secrets
import sys
import zipfile

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ROOT = os.path.dirname(os.path.abspath(__file__))
MP_DIR = os.path.join(ROOT, "miniprogram")

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".DS_Store"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def make_zip(out_path):
    print(f"Packing miniprogram -> {out_path}")
    count = 0
    total_size = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, f)
                rel = "miniprogram/" + os.path.relpath(full, MP_DIR).replace("\\", "/")
                z.write(full, rel)
                count += 1
                total_size += os.path.getsize(full)
    print(f"Packed {count} files, total {total_size//1024} KB, zip size {os.path.getsize(out_path)//1024} KB")


def upload(local_zip, remote_dir, fname):
    print(f"\nSSH {USER}@{HOST}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
                   allow_agent=False, look_for_keys=False)
    try:
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_dir}")
        stdout.channel.recv_exit_status()
        sftp = client.open_sftp()
        remote_path = f"{remote_dir}/{fname}"
        print(f"SFTP put -> {remote_path}")
        sftp.put(local_zip, remote_path)
        sftp.chmod(remote_path, 0o644)
        sftp.close()
        # 验证大小
        stdin, stdout, stderr = client.exec_command(f"ls -la {remote_path}")
        out = stdout.read().decode("utf-8")
        print(out.strip())
    finally:
        client.close()


def main():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd = secrets.token_hex(2)
    fname = f"miniprogram_{ts}_{rnd}.zip"
    local_zip = os.path.join(ROOT, fname)
    make_zip(local_zip)

    remote_dir = f"/home/ubuntu/{DEPLOY_ID}/uploads/miniprogram"
    upload(local_zip, remote_dir, fname)

    url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/miniprogram/{fname}"
    print(f"\nDownload URL: {url}")
    # 写入结果文件
    with open(os.path.join(ROOT, "_mp_optim_v1_url.txt"), "w", encoding="utf-8") as f:
        f.write(url + "\n")
    print("Wrote _mp_optim_v1_url.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
