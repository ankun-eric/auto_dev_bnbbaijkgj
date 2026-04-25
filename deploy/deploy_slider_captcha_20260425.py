"""[2026-04-25] 滑块验证码改造部署脚本

部署 Bug 修复："登录页字符验证码 → 滑块拼图验证码"
涉及端：backend + h5-web（商家 H5/PC） + admin-web（平台管理后台）。
用户端 H5 不动。

服务器项目目录不是 git 工作区，沿用 SFTP 上传 + docker compose 重建模式。
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

FILES = [
    # ===== 后端 =====
    "backend/app/services/slider_captcha_service.py",
    "backend/app/api/account_security.py",
    "backend/app/api/merchant_v1.py",
    "backend/app/api/admin.py",
    "backend/app/schemas/merchant_v1.py",
    "backend/tests/test_slider_captcha.py",
    "backend/static/captcha_bg/README.md",
    # ===== H5（商家 PC + 商家 H5） =====
    "h5-web/src/components/SliderCaptcha.tsx",
    "h5-web/src/lib/captcha.ts",
    "h5-web/src/app/merchant/login/page.tsx",
    "h5-web/src/app/merchant/m/login/page.tsx",
    # ===== Admin（平台管理后台） =====
    "admin-web/src/components/SliderCaptcha.tsx",
    "admin-web/src/lib/captcha.ts",
    "admin-web/src/app/login/page.tsx",
]


def _ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30,
              look_for_keys=False, allow_agent=False)
    return c


def _run(c: paramiko.SSHClient, cmd: str, timeout: int = 900) -> tuple[int, str, str]:
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
        print("== 上传滑块验证码改造文件 ==", flush=True)
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
            try:
                sftp.put(str(local), remote)
                ok += 1
                print(f"[ok] {rel}")
            except Exception as e:
                print(f"[FAIL] {rel}: {e}")
        print(f"上传完成: ok={ok} miss={miss}\n")

        print("== 重建 backend / admin-web / h5-web ==", flush=True)
        _run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend admin-web h5-web", timeout=1800)
        _run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend admin-web h5-web", timeout=300)

        print("== 等待容器启动 ==", flush=True)
        time.sleep(10)
        _run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps", timeout=30)

        print("== 后端日志 (tail) ==", flush=True)
        _run(c, f"docker logs --tail=80 {DEPLOY_ID}-backend", timeout=30)
    finally:
        sftp.close()
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
