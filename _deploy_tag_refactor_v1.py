"""[商品标签体系重构 v1.0 2026-05-20] 部署脚本

将本次改动的后端 + admin-web 文件上传到服务器，并重启对应容器。
迁移逻辑由后端启动时自动执行（main.py 的 lifespan）。
"""
from __future__ import annotations

import os
import sys
import time
import paramiko
from pathlib import Path

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_UUID}"
ROOT = Path(__file__).parent

# 改动文件清单
BACKEND_FILES = [
    "backend/app/models/models.py",
    "backend/app/api/product_admin.py",
    "backend/app/api/products.py",
    "backend/app/api/tag_recommend.py",
    "backend/app/schemas/products.py",
    "backend/app/schemas/tag_recommend.py",
    "backend/app/services/prd_tag_recommend_v1_migration.py",
    "backend/tests/test_tag_recommend_v1_20260520.py",
    "backend/tests/test_tag_system_refactor_v1_20260520.py",
]

ADMIN_FILES = [
    "admin-web/src/app/(admin)/product-system/tags/page.tsx",
    "admin-web/src/app/(admin)/product-system/products/page.tsx",
]

FLUTTER_FILES = [
    "flutter_app/lib/models/product.dart",
]


def ssh_connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-2000:])
    if err:
        print(f"STDERR: {err[-1500:]}")
    print(f"[exit={code}]")
    return code, out, err


def upload_files(ssh: paramiko.SSHClient, files: list[str]) -> None:
    sftp = ssh.open_sftp()
    for rel in files:
        local = ROOT / rel
        if not local.exists():
            print(f"WARN: local missing: {local}")
            continue
        remote = f"{PROJECT_DIR}/{rel}".replace("\\", "/")
        # 确保父目录存在
        parent = remote.rsplit("/", 1)[0]
        run(ssh, f"mkdir -p '{parent}'")
        sftp.put(str(local), remote)
        print(f"  UPLOADED {rel}")
    sftp.close()


def main() -> int:
    print(f"=== Deploy 标签体系重构 v1.0 to {HOST} ===")
    ssh = ssh_connect()

    # 1. 上传后端 / admin-web / flutter 文件
    print("\n--- Step 1: upload files ---")
    upload_files(ssh, BACKEND_FILES + ADMIN_FILES + FLUTTER_FILES)

    # 2. 重启 backend，触发迁移
    print("\n--- Step 2: restart backend ---")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker restart {PROJECT_UUID}-backend",
        timeout=120,
    )
    time.sleep(8)

    # 3. 等待 backend 健康
    for i in range(20):
        code, out, _ = run(
            ssh,
            f"docker logs --tail 60 {PROJECT_UUID}-backend 2>&1 | tail -60",
            timeout=60,
        )
        if "Application startup complete" in out or "Uvicorn running" in out:
            print("[backend] startup complete")
            break
        time.sleep(3)

    # 4. 验证迁移日志
    print("\n--- Step 3: check migration logs ---")
    run(
        ssh,
        f"docker logs {PROJECT_UUID}-backend 2>&1 | grep -E 'prd_tag_recommend_v1|symptom_tags|tag_columns|constitution' | tail -50",
        timeout=60,
    )

    # 5. 重新构建 admin-web（next.js 是 standalone build，需要重启容器，但我们直接 docker-compose up --build 太重）
    # 选择最轻量的方案：检查 admin 容器是否运行的是 dev mode，如是直接 restart 即可；否则做镜像内重新拷贝并重启
    print("\n--- Step 4: rebuild & restart admin-web ---")
    run(ssh, f"docker inspect -f '{{{{.Config.Cmd}}}}' {PROJECT_UUID}-admin 2>&1 | head -3")
    # 直接 docker compose up -d --build admin
    cmd = (
        f"cd {PROJECT_DIR} && "
        f"(docker compose build admin 2>&1 || docker-compose build admin 2>&1) | tail -40 && "
        f"(docker compose up -d admin 2>&1 || docker-compose up -d admin 2>&1) | tail -20"
    )
    run(ssh, cmd, timeout=900)
    time.sleep(5)

    # 6. 健康检查
    print("\n--- Step 5: health check ---")
    run(
        ssh,
        f"curl -s -o /dev/null -w 'backend:%{{http_code}}\\n' http://localhost/autodev/{PROJECT_UUID}/api/products?page=1\\&page_size=1",
        timeout=30,
    )
    run(
        ssh,
        f"curl -s -o /dev/null -w 'admin:%{{http_code}}\\n' http://localhost/autodev/{PROJECT_UUID}/admin/",
        timeout=30,
    )

    ssh.close()
    print("=== Deploy done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
