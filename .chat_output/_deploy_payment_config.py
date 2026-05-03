"""部署支付配置 PRD v1.0 到远程服务器。

通过 paramiko SSH/SFTP 上传变更文件，重启 / 重建容器并验证可达性。
"""
from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = Path(r"C:\auto_output\bnbbaijkgj")

BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


# 本次发生变更的文件清单（相对仓库根的路径）
FILES_BACKEND = [
    "backend/app/utils/crypto.py",
    "backend/app/models/models.py",
    "backend/app/schemas/payment_config.py",
    "backend/app/schemas/unified_orders.py",
    "backend/app/api/payment_config.py",
    "backend/app/api/payment_methods.py",
    "backend/app/api/unified_orders.py",
    "backend/app/services/schema_sync.py",
    "backend/app/main.py",
    "backend/tests/test_payment_config_v1.py",
]

FILES_ADMIN_WEB = [
    "admin-web/src/app/(admin)/payment-config/page.tsx",
    "admin-web/src/app/(admin)/layout.tsx",
    "admin-web/src/app/(admin)/product-system/orders/page.tsx",
]

FILES_H5_WEB = [
    "h5-web/src/app/unified-order/[id]/page.tsx",
]


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    return rc, out, err


def upload_file(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    # 确保父目录存在
    parts = remote.strip("/").split("/")
    cur = ""
    for p in parts[:-1]:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            try:
                sftp.mkdir(cur)
            except OSError:
                pass
    print(f"  -> {remote}")
    sftp.put(str(local), remote)


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST} ...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)
    sftp = client.open_sftp()

    # 1. 上传所有文件
    all_files = FILES_BACKEND + FILES_ADMIN_WEB + FILES_H5_WEB
    print(f"\n=== Uploading {len(all_files)} files ===")
    for rel in all_files:
        local = LOCAL_ROOT / rel
        if not local.exists():
            print(f"  !! missing local file: {rel}")
            continue
        remote = f"{REMOTE_ROOT}/{rel}".replace("\\", "/")
        upload_file(sftp, local, remote)

    sftp.close()

    # 2. 重启 backend 容器
    print("\n=== Restart backend ===")
    run(client, f"cd {REMOTE_ROOT} && docker compose restart backend", timeout=120)
    time.sleep(8)

    # 3. 重建 admin-web 容器
    print("\n=== Rebuild admin-web ===")
    run(
        client,
        f"cd {REMOTE_ROOT} && docker compose up -d --build --force-recreate admin-web",
        timeout=900,
    )

    # 4. 重建 h5-web 容器
    print("\n=== Rebuild h5-web ===")
    run(
        client,
        f"cd {REMOTE_ROOT} && docker compose up -d --build --force-recreate h5-web",
        timeout=900,
    )

    # 5. 验证关键 URL
    print("\n=== Verify ===")
    for path in ["/api/docs", "/admin/", "/admin/payment-config"]:
        url = f"{BASE_URL}{path}"
        run(
            client,
            f'curl -s -o /dev/null -w "{path} -> %{{http_code}}\\n" "{url}"',
            timeout=30,
        )

    # 6. 在 backend 容器中跑测试
    print("\n=== Run pytest in backend container ===")
    run(
        client,
        f"docker exec {DEPLOY_ID}-backend python -m pytest tests/test_payment_config_v1.py -v",
        timeout=300,
    )

    client.close()
    print("\n=== DONE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
