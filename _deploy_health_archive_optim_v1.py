"""[健康档案优化 PRD v1.0 2026-05-26] 部署脚本

将本次变更（后端 guardian_system.py / guardian_system_v12.py、H5
health-profile/page.tsx、i-guard/page.tsx，以及删除的 v13 与 guardian-system 目录）
增量同步到服务器，并重启 backend / h5 容器。
"""
from __future__ import annotations

import io
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

BACKEND_FILES = [
    "backend/app/api/guardian_system.py",
    "backend/app/api/guardian_system_v12.py",
    "backend/tests/test_guardian_system_v12.py",
]

H5_FILES = [
    "h5-web/src/app/health-profile/page.tsx",
    "h5-web/src/app/health-profile/i-guard/page.tsx",
]

H5_DELETE_DIRS = [
    "h5-web/src/app/health-profile/v13",
    "h5-web/src/app/guardian-system",
]

BACKEND_DELETE_FILES = [
    "backend/tests/test_guardian_system_v1.py",
]


def get_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run_remote(cli: paramiko.SSHClient, cmd: str, timeout: int = 600) -> int:
    print(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:])
    if err:
        print("[stderr]", err[-2000:])
    print(f"[exit {code}]")
    return code


def upload(sftp: paramiko.SFTPClient, local: str, remote: str) -> None:
    # 确保父目录存在
    parent = os.path.dirname(remote).replace("\\", "/")
    parts = parent.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass
    print(f"upload {local} -> {remote}")
    sftp.put(local, remote)


def main() -> int:
    for f in BACKEND_FILES + H5_FILES:
        if not os.path.exists(f):
            print(f"!! 缺失源文件: {f}")
            return 2

    cli = get_ssh()
    try:
        sftp = cli.open_sftp()
        print("=== 上传后端 ===")
        for f in BACKEND_FILES:
            upload(sftp, f, f"{REMOTE_DIR}/{f.replace(os.sep, '/')}")
        print("=== 上传 H5 ===")
        for f in H5_FILES:
            upload(sftp, f, f"{REMOTE_DIR}/{f.replace(os.sep, '/')}")
        sftp.close()

        print("=== 删除服务器旧目录与文件 ===")
        for d in H5_DELETE_DIRS:
            run_remote(cli, f"rm -rf {REMOTE_DIR}/{d}")
        for f in BACKEND_DELETE_FILES:
            run_remote(cli, f"rm -f {REMOTE_DIR}/{f}")

        print("=== 重启 backend 容器 ===")
        run_remote(cli, f"docker restart {DEPLOY_ID}-backend")

        print("=== 重新构建并启动 H5 容器（含 next build） ===")
        run_remote(
            cli,
            f"cd {REMOTE_DIR} && docker compose build h5 2>&1 | tail -60 && docker compose up -d h5 2>&1 | tail -20",
            timeout=1200,
        )

        time.sleep(15)
        run_remote(cli, f"docker ps --filter name={DEPLOY_ID}- --format '{{{{.Names}}}}\\t{{{{.Status}}}}'")
    finally:
        cli.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
