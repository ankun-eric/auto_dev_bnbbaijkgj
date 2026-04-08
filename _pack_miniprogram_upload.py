"""One-off: zip miniprogram, SFTP to server, verify HTTP 200."""
import os
import random
import zipfile
from datetime import datetime

import httpx
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
REMOTE_BASE = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
UPLOADS_SUBDIR = "uploads"
PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM_DIR = os.path.join(PROJECT_ROOT, "miniprogram")
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_hex = "".join(random.choices("0123456789abcdef", k=4))
    zip_name = f"miniprogram_{timestamp}_{rand_hex}.zip"
    zip_path = os.path.join(PROJECT_ROOT, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MINIPROGRAM_DIR):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__")]
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, MINIPROGRAM_DIR)
                zf.write(file_path, arcname)

    size = os.path.getsize(zip_path)
    print(f"打包完成: {zip_path}")
    print(f"文件大小: {size} bytes")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    try:
        stdin, stdout, stderr = client.exec_command(f"ls -la {REMOTE_BASE}/")
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print("--- 远程 ls ---")
        print(out or "(empty stdout)")
        if err.strip():
            print("stderr:", err)

        uploads_remote = f"{REMOTE_BASE}/{UPLOADS_SUBDIR}"
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {uploads_remote}")
        stderr.read()
        if stdout.channel.recv_exit_status() != 0:
            raise RuntimeError(f"mkdir failed: {stderr.read().decode()}")

        sftp = client.open_sftp()
        try:
            remote_file = f"{uploads_remote}/{zip_name}"
            sftp.put(zip_path, remote_file)
            print(f"已上传: {remote_file}")
        finally:
            sftp.close()
    finally:
        client.close()

    verify_url = f"{BASE_URL}/{UPLOADS_SUBDIR}/{zip_name}"
    r = httpx.get(verify_url, follow_redirects=True, timeout=60)
    print(f"HTTP {r.status_code} {verify_url}")
    if r.status_code != 200:
        raise SystemExit(f"验证失败: 期望 200，得到 {r.status_code}")

    print("\n下载 URL:")
    print(verify_url)


if __name__ == "__main__":
    main()
