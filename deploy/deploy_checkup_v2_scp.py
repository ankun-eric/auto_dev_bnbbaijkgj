"""[2026-04-23] 使用 SFTP 上传改动文件（绕过服务器访问 GitHub 受限）+ 重建容器。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

# 本次改动的文件清单（相对项目根目录）
FILES = [
    "backend/app/api/chat.py",
    "backend/app/api/ocr.py",
    "backend/app/main.py",
    "backend/app/api/checkup_api_v2.py",
    "h5-web/src/app/checkup/chat/[sessionId]/page.tsx",
    "h5-web/src/app/checkup/compare/select/page.tsx",
    "h5-web/src/app/checkup/detail/[id]/page.tsx",
    "h5-web/src/app/checkup/result/[id]/page.tsx",
]


def _ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return c


def _run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(f"$ {cmd}")
    if out.strip():
        print(out[:2000])
    if err.strip():
        print("stderr:", err[:2000])
    print(f"exit={code}\n")
    return code, out, err


def main() -> int:
    print("== SSH 连接 ==")
    c = _ssh()
    sftp = c.open_sftp()
    try:
        print("== 上传改动文件 ==")
        for rel in FILES:
            local = LOCAL_ROOT / rel
            remote = f"{PROJECT_DIR}/{rel}"
            if not local.exists():
                print(f"[skip] 本地不存在：{local}")
                continue
            # 确保远程目录存在
            remote_dir = remote.rsplit("/", 1)[0]
            _run(c, f"mkdir -p {remote_dir}", timeout=30)
            sftp.put(str(local), remote)
            print(f"[ok] {rel} -> {remote}")

        print("== 重建 backend + h5-web 容器 ==")
        _run(c, f"cd {PROJECT_DIR} && docker compose build backend h5-web 2>&1 | tail -30", timeout=1200)
        _run(c, f"cd {PROJECT_DIR} && docker compose up -d backend h5-web 2>&1 | tail -30", timeout=300)

        time.sleep(10)
        _run(c, "docker ps --format '{{.Names}}: {{.Status}}' | grep " + DEPLOY_ID, timeout=30)
        return 0
    finally:
        sftp.close()
        c.close()


if __name__ == "__main__":
    sys.exit(main())
