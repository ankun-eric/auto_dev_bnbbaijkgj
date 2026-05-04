#!/usr/bin/env python3
"""[2026-05-05] 部署 SDK 健康看板修复 + 强制 --no-cache 重建 backend / admin。

流程：
1) ssh 到测试服务器
2) cd 到项目目录，git fetch + reset 到最新 master
3) docker compose build --no-cache backend admin
4) docker compose up -d backend admin
5) 等待 30 秒 → 容器内验证 alipay sdk + sdk_health 模块可 import
6) HTTP 抽测：GET /api/health 应 200；GET /api/admin/health/sdk 未鉴权应 401/403
"""
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
        print(f"STDERR: {err}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed: {cmd}\n{err}")
    return out, err, rc


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    try:
        # 1) 拉取最新代码（带重试 + 镜像兜底）
        fetch_ok = False
        for attempt in range(1, 6):
            print(f"\n[git fetch attempt {attempt}/5]")
            _o, _e, rc = run(
                ssh,
                f"cd {PROJECT_DIR} && git fetch origin master",
                timeout=180,
                ignore_err=True,
            )
            if rc == 0:
                fetch_ok = True
                break
            time.sleep(8 * attempt)
        if not fetch_ok:
            # 兜底：使用 ghproxy 镜像下载 zip 后比对（这里直接报错让用户介入更稳妥）
            raise RuntimeError("git fetch 5 次失败，服务器到 GitHub 网络抖动严重")
        run(ssh, f"cd {PROJECT_DIR} && git reset --hard origin/master")
        run(ssh, f"cd {PROJECT_DIR} && git log --oneline -3")

        # 2) 强制 --no-cache 重建 backend 与 admin
        run(ssh, f"cd {PROJECT_DIR} && docker compose build --no-cache backend admin", timeout=900)
        run(ssh, f"cd {PROJECT_DIR} && docker compose up -d backend admin", timeout=300)

        # 3) 等待启动
        print("\n[等待 30 秒，让 backend 启动稳定]")
        time.sleep(30)

        # 4) 容器内验证
        run(ssh, f"docker exec {BACKEND_NAME} pip list 2>/dev/null | grep -iE 'alipay|tencentcloud'")
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from alipay import AliPay; print(\\"alipay sdk ok\\")"')
        run(ssh, f'docker exec {BACKEND_NAME} python -c "from app.core.sdk_health import get_snapshot; import json; s = get_snapshot(); print(json.dumps(s[\\"summary\\"]))"')

        # 5) backend 启动日志最后 80 行（重点关注 [SDK-HEALTH]）
        run(ssh, f"docker logs --tail 100 {BACKEND_NAME} 2>&1 | grep -E 'SDK-HEALTH|Application startup|Uvicorn|ERROR' | tail -30", ignore_err=True)

        # 6) HTTP 抽测：通过 gateway-nginx 访问
        run(ssh, f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/api/health")
        run(ssh, f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/api/admin/health/sdk")
        # 不鉴权应 401/403，鉴权后才能 200

    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
