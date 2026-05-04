#!/usr/bin/env python3
"""[2026-05-05] 文件已 SCP 上传，只跑 rebuild + 验证。"""
from __future__ import annotations

import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
BACKEND_NAME = f"{PROJECT_ID}-backend"
ADMIN_NAME = f"{PROJECT_ID}-admin"


def run(ssh, cmd, timeout=600, ignore_err=False):
    print(f"\n>>> {cmd}")
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err[-1000:]}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed: {cmd}")
    return out, err, rc


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    try:
        run(ssh, f"cd {PROJECT_DIR} && docker compose build --no-cache backend admin-web", timeout=1500)
        run(ssh, f"cd {PROJECT_DIR} && docker compose up -d backend admin-web", timeout=300)
        print("\n[等待 35 秒，让 backend/admin 启动]")
        time.sleep(35)

        run(ssh, f"docker exec {BACKEND_NAME} pip list 2>/dev/null | grep -iE 'alipay|tencentcloud'")
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from alipay import AliPay; print(\\"alipay sdk ok\\")"')
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from app.core.sdk_health import get_snapshot; import json; s = get_snapshot(); print(json.dumps(s[\\"summary\\"]))"')
        run(ssh, f"docker logs --tail 200 {BACKEND_NAME} 2>&1 | grep -E 'SDK-HEALTH|Application startup|Uvicorn|ERROR' | tail -30", ignore_err=True)

        base = f"http://localhost/autodev/{PROJECT_ID}"
        run(ssh, f"curl -s -o /dev/null -w 'health=%{{http_code}}\\n' {base}/api/health")
        run(ssh, f"curl -s -o /dev/null -w 'sdk_no_auth=%{{http_code}}\\n' {base}/api/admin/health/sdk")
        run(ssh, f"curl -s -o /dev/null -w 'admin_root=%{{http_code}}\\n' {base}/admin/")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
