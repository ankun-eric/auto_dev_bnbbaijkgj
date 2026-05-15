#!/usr/bin/env python3
"""[PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查功能 部署 + 验证。

流程：
  1. SSH 服务器
  2. git fetch + reset --hard origin/master
  3. 验证关键文件存在
  4. docker compose build backend h5-web admin-web
  5. docker compose up -d backend h5-web admin-web
  6. 等待容器健康
  7. 触发后端启动迁移：通过日志确认 _migrate_health_self_check_v1 已运行
  8. 用公网 BASE_URL 拉接口冒烟测试
"""
from __future__ import annotations
import sys
import time
from typing import Tuple

import paramiko
import requests

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"


def run(ssh, cmd: str, timeout: int = 1800) -> Tuple[int, str]:
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out_lines = []
    for line in iter(stdout.readline, ""):
        if not line:
            break
        sys.stdout.write(line)
        sys.stdout.flush()
        out_lines.append(line)
    code = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(f"[stderr] {err.strip()[:400]}")
    return code, "".join(out_lines)


def main():
    print(f"=== connect {HOST} ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                allow_agent=False, look_for_keys=False)
    try:
        # 1. pull latest
        for attempt in range(3):
            rc, out = run(ssh, f"cd {REMOTE_DIR} && timeout 180 git fetch origin master 2>&1 | tail -10", timeout=200)
            if "fatal" not in out and "unable to access" not in out:
                break
            time.sleep(5)
        run(ssh, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && git log -1 --oneline")

        # 2. 验证文件存在
        run(ssh, f"cd {REMOTE_DIR} && ls -la backend/app/api/health_self_check.py backend/app/schemas/health_self_check.py")
        run(ssh, f"cd {REMOTE_DIR} && grep -c 'PRD-HEALTH-SELF-CHECK-V1' backend/app/main.py || true")

        # 3. 构建 backend + h5-web + admin-web
        compose_files = ""
        rc, out = run(ssh, f"cd {REMOTE_DIR} && ls docker-compose.yml deploy/docker-compose.yml 2>/dev/null || true")
        if "deploy/docker-compose.yml" in out:
            compose_files = "-f deploy/docker-compose.yml"

        for svc in ("backend", "h5-web", "admin-web"):
            run(ssh, f"cd {REMOTE_DIR} && docker compose {compose_files} build {svc} 2>&1 | tail -30", timeout=1800)
        run(ssh, f"cd {REMOTE_DIR} && docker compose {compose_files} up -d backend h5-web admin-web 2>&1 | tail -20")

        # 4. 等待并查看 backend 启动日志（确认 migrate 函数已执行）
        print("\n=== 等待 backend 启动并迁移 ===")
        time.sleep(15)
        run(ssh, f"docker logs {PROJECT_ID}-backend --tail 80 2>&1 | tail -80")
        run(ssh, f"docker logs {PROJECT_ID}-backend 2>&1 | grep -i 'health_self_check\\|health-self-check\\|migrate' | tail -30")

        # 5. 冒烟测试公网接口
        print("\n=== 冒烟测试 ===")
        time.sleep(5)
        for path, exp in [
            (f"{BASE_URL}/api/health-self-check/dict", "body_parts"),
        ]:
            try:
                r = requests.get(path, timeout=20)
                print(f"GET {path} -> {r.status_code}")
                if r.status_code == 200:
                    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
                    print(f"  json keys: {list(body.keys()) if isinstance(body, dict) else type(body)}")
            except Exception as e:
                print(f"[error] {path}: {e}")

        # 6. 列出按钮中是否有新类型按钮
        try:
            r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
            print(f"GET /api/function-buttons -> {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                buttons = data if isinstance(data, list) else data.get('items', [])
                hsc = [b for b in buttons if b.get('button_type') == 'health_self_check']
                print(f"  health_self_check 按钮数: {len(hsc)}")
                if hsc:
                    print(f"  示例: {hsc[0]}")
        except Exception as e:
            print(f"[error] function-buttons: {e}")

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
