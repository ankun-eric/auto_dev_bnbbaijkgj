"""部署 PRD V1.0 (PC 后台优化) 到服务器

服务器目录不是 git 仓库，因此采用 tar 打包关键代码 → scp 上传 → 解压覆盖 →
重建相关 docker 容器的方式。

涉及目录：
- backend/app/  （后端）
- admin-web/src/  （管理后台前端）
- h5-web/src/  （商家 PC + H5 前端）
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "deploy"))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
COMPOSE = "docker-compose.prod.yml"


def run(ssh, cmd, timeout=900):
    print(f"\n$ {cmd[:240]}")
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out:
        print(out[-3000:])
    if err:
        print(f"[stderr] {err[-1500:]}")
    print(f"[exit {code}]")
    return out, err, code


def make_tar(local_paths: list[str], tar_path: Path) -> None:
    if tar_path.exists():
        tar_path.unlink()
    args = ["tar", "-czf", str(tar_path), "-C", str(ROOT)] + local_paths
    print(f"\n[tar] {' '.join(args[:6])} ... ({len(local_paths)} paths)")
    subprocess.run(args, check=True)
    size_kb = tar_path.stat().st_size // 1024
    print(f"[tar] 写入 {tar_path.name} ({size_kb} KB)")


def upload(ssh: paramiko.SSHClient, local: Path, remote: str) -> None:
    sftp = ssh.open_sftp()
    print(f"\n[scp] {local.name} -> {remote}")
    sftp.put(str(local), remote)
    sftp.close()


def main() -> int:
    ssh = create_client()
    try:
        # ────── 1. 打包并上传 backend ──────
        backend_tar = ROOT / "_pc_admin_optim_backend.tar.gz"
        make_tar(["backend/app", "backend/requirements.txt"], backend_tar)
        upload(ssh, backend_tar, f"{PROJECT_DIR}/_pc_admin_optim_backend.tar.gz")
        run(ssh, f"cd {PROJECT_DIR} && tar -xzf _pc_admin_optim_backend.tar.gz && rm _pc_admin_optim_backend.tar.gz")
        backend_tar.unlink(missing_ok=True)

        # ────── 2. 打包并上传 admin-web/src ──────
        admin_tar = ROOT / "_pc_admin_optim_admin.tar.gz"
        make_tar(["admin-web/src"], admin_tar)
        upload(ssh, admin_tar, f"{PROJECT_DIR}/_pc_admin_optim_admin.tar.gz")
        # admin-web 仅替换 src
        run(ssh, f"cd {PROJECT_DIR} && tar -xzf _pc_admin_optim_admin.tar.gz && rm _pc_admin_optim_admin.tar.gz")
        admin_tar.unlink(missing_ok=True)

        # ────── 3. 打包并上传 h5-web/src ──────
        h5_tar = ROOT / "_pc_admin_optim_h5.tar.gz"
        make_tar(["h5-web/src"], h5_tar)
        upload(ssh, h5_tar, f"{PROJECT_DIR}/_pc_admin_optim_h5.tar.gz")
        run(ssh, f"cd {PROJECT_DIR} && tar -xzf _pc_admin_optim_h5.tar.gz && rm _pc_admin_optim_h5.tar.gz")
        h5_tar.unlink(missing_ok=True)

        # ────── 4. 重建 backend ──────
        print("\n=== Build backend ===")
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE} build backend 2>&1 | tail -80",
            timeout=1500,
        )
        run(ssh, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE} up -d backend 2>&1 | tail -10")

        # ────── 5. 重建 admin-web ──────
        print("\n=== Build admin-web ===")
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE} build admin-web 2>&1 | tail -80",
            timeout=1500,
        )
        run(ssh, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE} up -d admin-web 2>&1 | tail -10")

        # ────── 6. 重建 h5-web ──────
        print("\n=== Build h5-web ===")
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE} build h5-web 2>&1 | tail -80",
            timeout=1500,
        )
        run(ssh, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE} up -d h5-web 2>&1 | tail -10")

        # ────── 7. 等待容器并查看后端日志 ──────
        print("\n=== 等待 25s 让容器就绪 ===")
        time.sleep(25)
        run(ssh, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")
        run(ssh, f"docker logs --tail 80 {DEPLOY_ID}-backend 2>&1 | tail -80")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
