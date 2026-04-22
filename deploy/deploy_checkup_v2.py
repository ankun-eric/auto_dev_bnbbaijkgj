"""[2026-04-23] 接口改造清单 v2 部署脚本。

- git push（本地）
- SSH 到服务器 → 项目目录
- git pull（重试 3 次）
- 重建 backend + h5-web 两个容器（不动 admin-web，因为本次没改 admin）
- 打印容器状态
"""
from __future__ import annotations

import sys
import time

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


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
        print(out)
    if err.strip():
        print("stderr:", err)
    print(f"exit={code}\n")
    return code, out, err


def main() -> int:
    print("== SSH 连接 ==")
    c = _ssh()
    try:
        # git pull 带重试
        for i in range(3):
            code, _, _ = _run(c, f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master", timeout=180)
            if code == 0:
                break
            print(f"[warn] git pull 第 {i+1} 次失败，5s 后重试...")
            time.sleep(5)
        else:
            print("[ERROR] git pull 连续 3 次失败")
            return 1

        # 查看当前 commit
        _run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=30)

        # 重建 backend 与 h5-web
        _run(c, f"cd {PROJECT_DIR} && docker compose build backend h5-web 2>&1 | tail -40", timeout=900)
        _run(c, f"cd {PROJECT_DIR} && docker compose up -d backend h5-web 2>&1 | tail -40", timeout=300)

        # 状态确认
        _run(c, "docker ps --format 'table {{.Names}}\\t{{.Status}}' | grep " + DEPLOY_ID, timeout=30)
        # backend 健康检查
        time.sleep(8)
        _run(c, f"docker exec {DEPLOY_ID}-backend sh -c 'curl -fsS http://localhost:8000/api/health || curl -fsS http://localhost:8000/health || echo health_check_none'", timeout=30)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
