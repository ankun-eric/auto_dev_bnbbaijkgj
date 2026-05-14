#!/usr/bin/env python3
"""Quick redeploy of backend container only + re-run tests."""
from __future__ import annotations
import sys, time
from typing import List, Tuple
import paramiko
import requests

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600):
    print(f"\n>>> SSH: {cmd[:140]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out_lines = []
    for line in iter(stdout.readline, ""):
        if not line: break
        sys.stdout.write(line); sys.stdout.flush()
        out_lines.append(line)
    return stdout.channel.recv_exit_status(), "".join(out_lines), stderr.read().decode("utf-8", "replace")


def deploy():
    print(f"=== 连接 {HOST} ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    try:
        run(ssh, f"cd {REMOTE_DIR} && git fetch origin master 2>&1 | tail -10")
        run(ssh, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && git log -2 --oneline")

        # backend only
        run(ssh, f"cd {REMOTE_DIR} && (docker compose stop backend 2>&1 || docker-compose stop backend 2>&1) | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && (docker compose rm -f backend 2>&1 || docker-compose rm -f backend 2>&1) | tail -5")
        code, _, _ = run(
            ssh,
            f"cd {REMOTE_DIR} && (docker compose build backend 2>&1 || docker-compose build backend 2>&1) | tail -50",
            timeout=1800,
        )
        run(ssh, f"cd {REMOTE_DIR} && (docker compose up -d backend 2>&1 || docker-compose up -d backend 2>&1) | tail -10")

        # 等 backend 健康
        for i in range(45):
            try:
                r = requests.get(f"{BASE_URL}/api/health", timeout=10, verify=True)
                if r.status_code in (200, 404):
                    print(f"[OK] backend OK (第{i+1}次, HTTP {r.status_code})")
                    break
            except Exception: pass
            time.sleep(2)

        # 打印日志中的 migrate 信息
        run(ssh, f"docker logs --tail 300 {PROJECT_ID}-backend 2>&1 | grep -E 'migrate|aichat' | tail -30 || true")
    finally:
        ssh.close()


if __name__ == "__main__":
    deploy()
    # 测试
    print(f"\n=== 自动化测试 {BASE_URL} ===\n")
    results = []

    def t(name, fn):
        try: results.append((name, *fn()))
        except Exception as e: results.append((name, False, f"异常 {e}"))

    # T1
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=15)
        t("T1 /api/health", lambda: (r.status_code == 200, f"HTTP {r.status_code}"))
    except Exception as e: t("T1 /api/health", lambda: (False, str(e)))

    # T3
    try:
        r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
        ok = r.status_code == 200 and isinstance(r.json(), list)
        t("T3 公开 /api/function-buttons", lambda: (ok, f"HTTP {r.status_code} 返回 {len(r.json()) if ok else '?' } 条"))
    except Exception as e: t("T3", lambda: (False, str(e)))

    # T10 migrate log
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, 22, USER, PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
        _, stdout, _ = ssh.exec_command(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -i 'aichat_optim_fix_v1' | tail -10", timeout=30)
        out = stdout.read().decode("utf-8", "replace")
        ssh.close()
        t("T10 启动日志含 aichat_optim_fix_v1", lambda: (bool(out.strip()), out.strip()[:300]))
    except Exception as e: t("T10", lambda: (False, str(e)))

    # T12 func_grid migration log
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, 22, USER, PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
        _, stdout, _ = ssh.exec_command(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -iE 'func_grid|simplified' | tail -10", timeout=30)
        out = stdout.read().decode("utf-8", "replace")
        ssh.close()
        t("T12 启动日志含 func_grid 迁移", lambda: (bool(out.strip()), out.strip()[:300]))
    except Exception as e: t("T12", lambda: (False, str(e)))

    print("\n=== 结果 ===")
    fail = 0
    for name, ok, info in results:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name} - {info}")
        if not ok: fail += 1
    sys.exit(1 if fail else 0)
