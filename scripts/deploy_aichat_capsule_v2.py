#!/usr/bin/env python3
"""
[PRD-AICHAT-CAPSULE-V2 2026-05-15] 远程部署 + 验证脚本

用途：将代码 rsync 到服务器、重新构建并启动 docker-compose、验证关键 URL 可达。
"""
import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path


REMOTE_HOST = "newbb.test.bangbangvip.com"
REMOTE_USER = "ubuntu"
REMOTE_PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PATH = f"/home/ubuntu/projects/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def run_ssh(cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    full = [
        "sshpass", "-p", REMOTE_PASSWORD, "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{REMOTE_USER}@{REMOTE_HOST}",
        cmd,
    ]
    proc = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def http_check(path: str, expect_codes: tuple[int, ...] = (200, 301, 302)) -> tuple[bool, int]:
    url = f"{BASE_URL}{path}"
    try:
        r = subprocess.run(
            ["curl", "-skLI", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=30,
        )
        code = int((r.stdout or "0").strip() or 0)
        return code in expect_codes, code
    except Exception:
        return False, 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    print(f"[deploy] BASE_URL = {BASE_URL}")

    # 1) 拉取最新代码（远端通过 git）
    print("[deploy] step 1: git pull on server")
    cmds = [
        f"cd {REMOTE_PATH} && git fetch --all && git reset --hard origin/master",
    ]
    for c in cmds:
        rc, out, err = run_ssh(c, timeout=300)
        print(out[-2000:] if out else "")
        if err:
            print("STDERR:", err[-2000:], file=sys.stderr)
        if rc != 0:
            print(f"[deploy] step1 failed rc={rc}")
            return 2

    # 2) 重新构建后端 + admin-web + h5-web 并启动
    if not args.skip_build:
        print("[deploy] step 2: docker compose build & up")
        rc, out, err = run_ssh(
            f"cd {REMOTE_PATH} && docker compose up -d --build backend admin-web h5-web 2>&1 | tail -200",
            timeout=1800,
        )
        print(out[-4000:] if out else "")
        if err:
            print("STDERR:", err[-2000:], file=sys.stderr)
        if rc != 0:
            print(f"[deploy] step2 failed rc={rc}")
            return 2

    # 3) 等容器健康
    print("[deploy] step 3: wait 25s for containers to settle")
    time.sleep(25)

    # 4) 健康检查
    paths = [
        ("/api/docs", (200, 301, 302)),
        ("/api/function-buttons", (200,)),
        ("/admin/", (200, 301, 302)),
        ("/ai-home", (200, 301, 302)),
    ]
    print("[deploy] step 4: health check")
    all_ok = True
    for p, codes in paths:
        ok, code = http_check(p, codes)
        print(f"  {p:32s} HTTP {code} {'OK' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    if not all_ok:
        print("[deploy] FAIL: some health checks failed")
        return 3
    print("[deploy] ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
