"""打包 miniprogram 目录为 zip，上传到服务器并验证。"""
import os
import secrets
import time
import zipfile
from pathlib import Path

import paramiko

LOCAL_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
MP_DIR = LOCAL_ROOT / "miniprogram"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    fname = f"miniprogram_paymentconfig_{ts}_{rand}.zip"
    out_path = LOCAL_ROOT / fname

    # 排除 dist / node_modules / .git 等
    EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build", "miniprogram_npm"}

    print(f"Packing {MP_DIR} -> {fname}")
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            # 排除目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                p = Path(root) / f
                rel = p.relative_to(MP_DIR.parent)  # 保留 miniprogram/ 前缀
                zf.write(p, rel.as_posix())
                count += 1
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"Packed {count} files, {size_mb:.2f} MB")

    # SFTP 上传到 /home/ubuntu/<deploy>/miniprogram/<fname>
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = cli.open_sftp()
    remote_dir = f"{REMOTE_ROOT}/miniprogram"
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)
    remote = f"{remote_dir}/{fname}"
    print(f"Uploading -> {remote}")
    sftp.put(str(out_path), remote)
    sftp.chmod(remote, 0o644)
    sftp.close()

    # 通过 docker exec gateway 验证（gateway 容器代理 /miniprogram/...）
    # 用 curl 直接访问外网 URL
    url = f"{BASE_URL}/miniprogram/{fname}"
    print(f"Verify: {url}")
    stdin, stdout, _ = cli.exec_command(
        f'curl -s -o /dev/null -w "%{{http_code}}" "{url}"', timeout=30
    )
    code = stdout.read().decode().strip()
    print(f"  http_code = {code}")
    cli.close()

    print(f"\nFINAL_URL={url}")
    print(f"FINAL_FILE={fname}")
    return url, fname


if __name__ == "__main__":
    main()
