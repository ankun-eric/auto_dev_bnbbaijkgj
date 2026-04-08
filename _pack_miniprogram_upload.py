"""Zip miniprogram, SFTP to server host, docker cp into backend uploads, verify HTTP 200."""
import os
import random
import zipfile
from datetime import datetime

import httpx
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = os.environ.get("MINIPROGRAM_SSH_PASSWORD", "Bangbang987")
REMOTE_BASE = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
UPLOADS_SUBDIR = "uploads"
PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM_DIR = os.path.join(PROJECT_ROOT, "miniprogram")
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def _backend_container_name(client: paramiko.SSHClient) -> str:
    _, stdout, _ = client.exec_command(
        "docker ps --format '{{.Names}}' | grep -E '3b7b999d.*backend' | head -1"
    )
    name = stdout.read().decode().strip()
    return name or "3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend"


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
        print("--- 远程 ls ---")
        print(out or "(empty stdout)")

        uploads_remote = f"{REMOTE_BASE}/{UPLOADS_SUBDIR}"
        client.exec_command(f"mkdir -p {uploads_remote}")

        sftp = client.open_sftp()
        try:
            remote_host_file = f"{uploads_remote}/{zip_name}"
            sftp.put(zip_path, remote_host_file)
            print(f"已上传到主机: {remote_host_file}")
        finally:
            sftp.close()

        cname = _backend_container_name(client)
        print(f"后端容器: {cname}")
        inner_path = f"/app/uploads/{zip_name}"
        docker_cp = f"docker cp {uploads_remote}/{zip_name} {cname}:{inner_path}"
        _, stdout, stderr = client.exec_command(docker_cp)
        stderr.read()
        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError(f"docker cp 失败 exit={code}: {stderr.read().decode()}")
        print(f"已复制进容器: {cname}:{inner_path}")
    finally:
        client.close()

    verify_url = f"{BASE_URL}/{UPLOADS_SUBDIR}/{zip_name}"
    r = httpx.get(verify_url, follow_redirects=True, timeout=60)
    print(f"HTTP {r.status_code} {verify_url}")
    if r.status_code != 200:
        raise SystemExit(f"验证失败: 期望 200，得到 {r.status_code}")
    if len(r.content) != size:
        print(f"警告: 响应体大小 {len(r.content)} 与本地 {size} 不一致")

    print("\n下载 URL:")
    print(verify_url)


if __name__ == "__main__":
    main()
