#!/usr/bin/env python3
"""[2026-05-05] 部署 SDK 健康看板修复（绕过 GitHub）：使用 SCP 直接上传必要文件。

由于服务器到 github.com 网络阻断（fetch 超时），改为：
1) SCP 上传本次新增/修改的关键文件到服务器项目目录
2) 容器内 docker compose build --no-cache backend admin
3) docker compose up -d backend admin
4) 验证
"""
from __future__ import annotations

import os
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

LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

# 本次涉及的文件（新增 + 修改）
FILES_TO_UPLOAD: list[tuple[str, str]] = [
    # (本地相对路径, 远程绝对目标路径)
    ("backend/app/core/sdk_health.py", f"{PROJECT_DIR}/backend/app/core/sdk_health.py"),
    ("backend/app/api/admin_sdk_health.py", f"{PROJECT_DIR}/backend/app/api/admin_sdk_health.py"),
    ("backend/app/main.py", f"{PROJECT_DIR}/backend/app/main.py"),
    ("backend/app/services/alipay_service.py", f"{PROJECT_DIR}/backend/app/services/alipay_service.py"),
    ("backend/requirements.txt", f"{PROJECT_DIR}/backend/requirements.txt"),
    ("backend/tests/test_sdk_health_v1.py", f"{PROJECT_DIR}/backend/tests/test_sdk_health_v1.py"),
    ("admin-web/src/components/SdkHealthCard.tsx", f"{PROJECT_DIR}/admin-web/src/components/SdkHealthCard.tsx"),
    ("admin-web/src/app/(admin)/system/sdk-health/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/system/sdk-health/page.tsx"),
    ("admin-web/src/app/(admin)/payment-config/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/payment-config/page.tsx"),
    ("admin-web/src/app/(admin)/layout.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/layout.tsx"),
]


def run(ssh, cmd, timeout=600, ignore_err=False):
    print(f"\n>>> {cmd}")
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed: {cmd}\n{err}")
    return out, err, rc


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)

    sftp = ssh.open_sftp()
    try:
        # 1) 上传本次涉及的文件
        for local_rel, remote_abs in FILES_TO_UPLOAD:
            local_abs = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.isfile(local_abs):
                raise FileNotFoundError(local_abs)
            # 确保远程父目录存在
            remote_dir = os.path.dirname(remote_abs)
            run(ssh, f'mkdir -p "{remote_dir}"', ignore_err=True)
            print(f"[scp] {local_abs} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        # 2) 验证服务器上 alipay_service.py 是否已是新版（包含 try/except for AliPayCert）
        run(ssh, f'grep -n "from alipay import AliPayCert" {PROJECT_DIR}/backend/app/services/alipay_service.py', ignore_err=True)
        run(ssh, f'grep -n "AliPayCert" {PROJECT_DIR}/backend/app/services/alipay_service.py | head -5', ignore_err=True)

        # 3) 强制 --no-cache 重建 backend 与 admin-web
        run(ssh, f"cd {PROJECT_DIR} && docker compose build --no-cache backend admin-web", timeout=1500)
        run(ssh, f"cd {PROJECT_DIR} && docker compose up -d backend admin-web", timeout=300)

        # 4) 等待启动
        print("\n[等待 30 秒，让 backend 启动稳定]")
        time.sleep(30)

        # 5) 容器内验证
        run(ssh, f"docker exec {BACKEND_NAME} pip list 2>/dev/null | grep -iE 'alipay|tencentcloud'")
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from alipay import AliPay; print(\\"alipay sdk ok\\")"')
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from app.core.sdk_health import get_snapshot; import json; s = get_snapshot(); print(json.dumps(s[\\"summary\\"]))"')

        # 6) backend 启动日志重点
        run(ssh, f"docker logs --tail 200 {BACKEND_NAME} 2>&1 | grep -E 'SDK-HEALTH|Application startup|Uvicorn|ERROR' | tail -30", ignore_err=True)

        # 7) HTTP 抽测
        base = f"http://localhost/autodev/{PROJECT_ID}"
        run(ssh, f"curl -s -o /dev/null -w 'health=%{{http_code}}\\n' {base}/api/health")
        run(ssh, f"curl -s -o /dev/null -w 'sdk_no_auth=%{{http_code}}\\n' {base}/api/admin/health/sdk")
        run(ssh, f"curl -s -o /dev/null -w 'admin_root=%{{http_code}}\\n' {base}/admin/")
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
