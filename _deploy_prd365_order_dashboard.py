"""[PRD-365 商家后台「预约看板」替换升级 v1.0] 远程部署 + 服务器侧测试脚本

流程：
1. paramiko SFTP 上传本次改动的文件到服务器项目目录
2. docker compose build h5-web admin-web backend
3. docker compose up -d --force-recreate h5-web admin-web backend
4. 容器内执行新增 pytest 用例（test_prd365_new_appointment_notify_v1.py）
5. gateway nginx -s reload
6. 关键 URL HTTPS 健康检查
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

# 本次改动的文件清单（相对项目根）
FILES = [
    "h5-web/src/app/merchant/order-dashboard/page.tsx",
    "h5-web/src/app/merchant/calendar/page.tsx",
    "h5-web/src/app/merchant/layout.tsx",
    "admin-web/src/app/(admin)/merchant/stores/page.tsx",
    "admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx",
    "backend/app/services/merchant_new_appointment_notify.py",
    "backend/app/api/unified_orders.py",
    "backend/tests/test_prd365_new_appointment_notify_v1.py",
]


def exec_cmd(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[exec] {cmd[:160]}{'...' if len(cmd) > 160 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-2000:])
    if err and code != 0:
        print("[stderr]", err[-2000:])
    return code, out, err


def main() -> int:
    # 1) SSH + SFTP 连接
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    client.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    sftp = client.open_sftp()

    # 2) 上传文件
    repo_root = Path(__file__).resolve().parent
    print(f"[upload] repo_root={repo_root}")
    for rel in FILES:
        local = repo_root / rel
        remote = f"{PROJECT_DIR}/{rel}".replace("\\", "/")
        if not local.exists():
            print(f"  - SKIP missing local: {local}")
            continue
        # 确保远端目录存在
        remote_dir = "/".join(remote.split("/")[:-1])
        exec_cmd(client, f"mkdir -p '{remote_dir}'")
        print(f"  ↑ {rel}  ({local.stat().st_size} bytes)")
        sftp.put(str(local), remote)

    sftp.close()

    # 3) 拉镜像 + build
    print("\n=== docker compose build ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose build backend admin-web h5-web 2>&1 | tail -120",
        timeout=900,
    )
    if rc != 0:
        print("[fail] docker compose build 失败")
        return 1

    # 4) up -d
    print("\n=== docker compose up -d --force-recreate ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose up -d --force-recreate backend admin-web h5-web 2>&1 | tail -60",
        timeout=300,
    )
    if rc != 0:
        print("[warn] up -d 退出非零，继续后续验证")

    # 等待容器就绪
    time.sleep(8)

    # 5) 容器内 pytest
    print("\n=== 容器内 pytest 新预约通知用例 ===")
    backend_container = f"{DEPLOY_ID}-backend"
    # 先确保 pytest 可用
    exec_cmd(
        client,
        f"docker exec {backend_container} pip install -q pytest pytest-asyncio httpx 2>&1 | tail -20",
        timeout=180,
    )
    rc, out, err = exec_cmd(
        client,
        f"docker exec {backend_container} bash -lc "
        f"'cd /app && python -m pytest tests/test_prd365_new_appointment_notify_v1.py -v --noconftest -p no:cacheprovider 2>&1'",
        timeout=300,
    )
    pytest_ok = rc == 0
    print(f"[pytest] 退出码={rc} 通过={pytest_ok}")

    # 6) gateway nginx reload
    print("\n=== gateway nginx reload ===")
    exec_cmd(client, "docker exec gateway nginx -t 2>&1 | tail -10", timeout=30)
    exec_cmd(client, "docker exec gateway nginx -s reload 2>&1 | tail -10", timeout=30)

    # 7) HTTPS smoke
    print("\n=== HTTPS smoke ===")
    urls = [
        f"{BASE_URL}/",
        f"{BASE_URL}/admin/",
        f"{BASE_URL}/admin/merchant/stores/",
        f"{BASE_URL}/admin/product-system/orders/dashboard/",
        f"{BASE_URL}/merchant/order-dashboard/",
        f"{BASE_URL}/merchant/calendar/",
        f"{BASE_URL}/api/openapi.json",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
    ]
    for u in urls:
        exec_cmd(client, f"curl -k -s -o /dev/null -w '{u} -> %{{http_code}}\\n' '{u}'", timeout=20)

    client.close()
    print("\n=== 部署完成 ===")
    print("pytest_ok=", pytest_ok)
    return 0 if pytest_ok else 2


if __name__ == "__main__":
    sys.exit(main())
