"""[2026-04-25] perf v1 (commit cca757a) 部署脚本：SFTP 上传 + 重建 backend/h5。

服务器项目目录不是 git 工作区，因此沿用项目惯例：通过 SFTP 上传本次 commit 涉及
的源码文件（仅 backend / h5-web），然后 docker compose 重建 backend / h5-web。
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

# commit cca757a 涉及的、需上传到服务器容器构建上下文中的文件
FILES = [
    # 后端
    "backend/app/api/report_interpret.py",
    "backend/tests/test_report_interpret_perf_v1.py",
    # H5
    "h5-web/src/app/chat/[sessionId]/page.tsx",
    "h5-web/src/app/checkup/page.tsx",
    "h5-web/src/lib/image-compress.ts",
    # 小程序 / Flutter 同步源码（不影响容器，但保持仓库一致）
    "miniprogram/pages/chat/index.js",
    "miniprogram/pages/chat/index.wxml",
    "miniprogram/pages/chat/index.wxss",
    "miniprogram/pages/checkup/index.js",
    "miniprogram/utils/image-compress.js",
    "flutter_app/lib/providers/health_provider.dart",
    "flutter_app/lib/screens/ai/chat_screen.dart",
    "flutter_app/lib/utils/image_compress_util.dart",
]


def _ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def _run(c: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(f"$ {cmd}")
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print("stderr:", err[-1500:])
    print(f"exit={code}\n", flush=True)
    return code, out, err


def main() -> int:
    print("== SSH 连接 ==", flush=True)
    c = _ssh()
    sftp = c.open_sftp()
    try:
        print("== 上传改动文件 (commit cca757a) ==", flush=True)
        ok = miss = 0
        for rel in FILES:
            local = LOCAL_ROOT / rel
            remote = f"{PROJECT_DIR}/{rel}"
            if not local.exists():
                print(f"[skip] 本地不存在: {local}")
                miss += 1
                continue
            remote_dir = remote.rsplit("/", 1)[0]
            _run(c, f"mkdir -p '{remote_dir}'", timeout=30)
            sftp.put(str(local), remote)
            print(f"[ok] {rel}")
            ok += 1
        print(f"上传汇总: ok={ok} miss={miss}", flush=True)

        print("\n== 远端校验 backend/app/api/report_interpret.py 三个新端点 ==", flush=True)
        _run(
            c,
            f"grep -nE '/session/.+/task-status|/session/.+/ocr-detail|/ocr-detail/click' "
            f"{PROJECT_DIR}/backend/app/api/report_interpret.py | head -20",
        )

        print("\n== 重建 backend / h5-web ==", flush=True)
        _run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend h5-web 2>&1 | tail -60",
            timeout=1800,
        )
        _run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1 | tail -30",
            timeout=300,
        )

        print("\n== 等待 backend 健康 ==", flush=True)
        for i in range(1, 25):
            code, out, _ = _run(
                c,
                f"docker inspect -f '{{{{.State.Health.Status}}}}' {DEPLOY_ID}-backend 2>/dev/null "
                f"|| docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-backend",
                timeout=15,
            )
            state = out.strip().splitlines()[-1] if out.strip() else ""
            print(f"[{i}] backend state = {state}")
            if state in ("healthy", "running"):
                break
            time.sleep(5)

        _run(c, f"docker compose -f {PROJECT_DIR}/docker-compose.prod.yml -p {DEPLOY_ID} ps 2>&1 | tail -20", timeout=30)
        _run(c, f"docker logs --tail 60 {DEPLOY_ID}-backend 2>&1 | tail -60", timeout=30)
        _run(c, f"docker logs --tail 30 {DEPLOY_ID}-h5 2>&1 | tail -30", timeout=30)

        print("\n== 把 gateway-nginx 加入项目网络 ==", flush=True)
        _run(
            c,
            f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || echo 'already connected or n/a'",
        )
        _run(
            c,
            f"docker network connect {DEPLOY_ID}_{DEPLOY_ID}-network gateway-nginx 2>/dev/null || echo 'n/a'",
        )
        _run(
            c,
            f"docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}' 2>/dev/null || true",
        )
        _run(
            c,
            f"docker network inspect {DEPLOY_ID}_{DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}' 2>/dev/null || true",
        )

        # 强制 gateway 重新解析上游
        _run(c, "docker exec gateway-nginx nginx -s reload 2>&1 || true", timeout=20)

        print("\n== 接口可达性验证 ==", flush=True)
        base = f"https://{HOST}/autodev/{DEPLOY_ID}"
        urls = [
            ("task-status", f"GET  {base}/api/report/interpret/session/1/task-status"),
            ("ocr-detail", f"GET  {base}/api/report/interpret/session/1/ocr-detail"),
            ("ocr-click", f"POST {base}/api/report/interpret/ocr-detail/click"),
            ("h5-home", f"GET  {base}/"),
            ("h5-checkup", f"GET  {base}/checkup"),
        ]
        for name, line in urls:
            method, url = line.split(maxsplit=1)
            url = url.strip()
            if method == "POST":
                cmd = f"curl -sk -o /dev/null -w '%{{http_code}}' -X POST -H 'Content-Type: application/json' -d '{{}}' '{url}'"
            else:
                cmd = f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'"
            _, out, _ = _run(c, cmd, timeout=30)
            print(f"  [{name}] -> {out.strip()}\n", flush=True)

        return 0
    finally:
        sftp.close()
        c.close()


if __name__ == "__main__":
    sys.exit(main())
