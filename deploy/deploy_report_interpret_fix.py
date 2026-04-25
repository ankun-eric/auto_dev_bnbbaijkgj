"""[2026-04-25] 体检报告解读 Bug 修复部署脚本（三端+后端+Nginx）。

使用 SFTP 上传改动文件，然后重建 backend/h5-web/admin 容器，
最后更新 gateway-nginx 的 SSE 专用 location 并 reload。
"""
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

# 本次改动需要上传的文件（相对项目根）
FILES = [
    # 后端
    "backend/app/api/chat.py",
    "backend/app/api/report_interpret.py",
    "backend/app/main.py",
    "backend/app/models/models.py",
    "backend/app/services/report_interpret_migration.py",
    "backend/app/core/task_queue.py",
    "backend/tests/test_report_interpret_fix.py",
    # H5
    "h5-web/src/app/chat/[sessionId]/page.tsx",
    # 小程序
    "miniprogram/pages/chat/index.js",
    "miniprogram/pages/chat/index.wxml",
    "miniprogram/pages/chat/index.wxss",
    # Flutter（仅用于源码同步，服务器不打包）
    "flutter_app/lib/screens/ai/chat_screen.dart",
    "flutter_app/lib/services/sse_service.dart",
    # Nginx 配置（会被 gateway 应用）
    "nginx.conf",
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
        print(out[:3000])
    if err.strip():
        print("stderr:", err[:1500])
    print(f"exit={code}\n")
    return code, out, err


def main() -> int:
    print("== SSH 连接 ==")
    c = _ssh()
    sftp = c.open_sftp()
    try:
        print("== 上传改动文件 ==")
        ok, miss = 0, 0
        for rel in FILES:
            local = LOCAL_ROOT / rel
            remote = f"{PROJECT_DIR}/{rel}"
            if not local.exists():
                print(f"[skip] 本地不存在：{local}")
                miss += 1
                continue
            remote_dir = remote.rsplit("/", 1)[0]
            _run(c, f"mkdir -p {remote_dir}", timeout=30)
            sftp.put(str(local), remote)
            print(f"[ok] {rel}")
            ok += 1
        print(f"文件上传完成：ok={ok} miss={miss}")

        print("== 重建 backend/h5/admin 容器 ==")
        _run(c, f"cd {PROJECT_DIR} && docker compose build backend h5-web admin-web 2>&1 | tail -40", timeout=1500)
        _run(c, f"cd {PROJECT_DIR} && docker compose up -d backend h5-web admin-web 2>&1 | tail -40", timeout=300)

        time.sleep(12)
        _run(c, f"docker ps --format '{{{{.Names}}}}: {{{{.Status}}}}' | grep {DEPLOY_ID}", timeout=30)
        _run(c, f"docker logs --tail 40 {DEPLOY_ID}-backend 2>&1 | tail -40", timeout=30)

        print("== 更新 gateway-nginx SSE 配置（如 gateway-nginx 容器存在） ==")
        # 上传项目 nginx.conf 到约定位置，供 gateway include
        gateway_conf_remote = f"/home/ubuntu/autodev/{DEPLOY_ID}.conf"
        _run(c, "mkdir -p /home/ubuntu/autodev", timeout=10)
        try:
            sftp.put(str(LOCAL_ROOT / "nginx.conf"), gateway_conf_remote)
            print(f"[ok] gateway conf uploaded: {gateway_conf_remote}")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] gateway conf upload skipped: {e}")

        # 尝试 reload gateway-nginx
        _run(c, "docker ps --format '{{.Names}}' | grep -i gateway || true", timeout=10)
        _run(c, "docker exec gateway-nginx nginx -t 2>&1 || true", timeout=20)
        _run(c, "docker exec gateway-nginx nginx -s reload 2>&1 || true", timeout=20)

        print("== 健康探测 ==")
        _run(
            c,
            f"curl -sk -o /dev/null -w 'h5=%{{http_code}} api=%{{http_code}}\\n' "
            f"https://{HOST}/autodev/{DEPLOY_ID}/checkup",
            timeout=30,
        )
        return 0
    finally:
        sftp.close()
        c.close()


if __name__ == "__main__":
    sys.exit(main())
