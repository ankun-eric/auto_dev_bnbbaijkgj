# -*- coding: utf-8 -*-
"""[2026-05-02 卡功能 v1.1 第 1 期] 重新部署：先确保 git fetch 成功拉到 32f218b，再 build。"""
from __future__ import annotations
import os
import sys
import time
import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NETWORK = f"{DEPLOY_ID}-network"
GATEWAY = "gateway"
COMPOSE_FILE = "docker-compose.prod.yml"
BACKEND_CONT = f"{DEPLOY_ID}-backend"
EXPECTED_COMMIT = "32f218b"

GIT_TOKEN = os.environ.get("GIT_TOKEN") or os.environ.get("GH_TOKEN", "")
GIT_URL_TOKEN = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN else
    "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return c


def run(c, cmd: str, timeout: int = 300):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:], flush=True)
    if err.strip():
        print("stderr:", err[-1500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def fetch_until_latest(c) -> bool:
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL_TOKEN}", timeout=15)
    for attempt in range(1, 7):
        print(f"\n--- git fetch attempt {attempt}/6 ---", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 180 "
            f"git -c http.postBuffer=524288000 fetch --depth=10 origin master 2>&1",
            timeout=240)
        _, out, _ = run(c,
            f"cd {PROJECT_DIR} && git log -1 origin/master --format=%h",
            timeout=10)
        head = out.strip().split()[-1] if out.strip() else ""
        print(f"  origin/master HEAD = {head}, expected starts with {EXPECTED_COMMIT}", flush=True)
        if head.startswith(EXPECTED_COMMIT):
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(5)
    return False


def main() -> int:
    c = ssh()
    try:
        # 先确认服务器现状
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)

        if not fetch_until_latest(c):
            print("!! git fetch 6 次仍未拉到 32f218b，部署终止", flush=True)
            return 1

        print("\n== 重建 backend ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build backend 2>&1 | tail -20",
            timeout=900)

        print("\n== 重建 h5-web ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build h5-web 2>&1 | tail -20",
            timeout=1500)

        print("\n== 重建 admin-web ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build admin-web 2>&1 | tail -20",
            timeout=1500)

        print("\n== up -d ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend admin-web h5-web 2>&1 | tail -20",
            timeout=180)

        for i in range(20):
            time.sleep(5)
            _, out, _ = run(c,
                f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}",
                timeout=10)
            lines = [ln for ln in out.splitlines() if ln.strip()]
            ok = (lines
                  and any("backend" in ln for ln in lines)
                  and not any("starting" in ln.lower() or "unhealthy" in ln.lower() for ln in lines))
            print(f"  [{i+1}/20] ok={ok}", flush=True)
            if ok and i >= 2:
                break

        print("\n== gateway reload ==", flush=True)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1 || true", timeout=15)

        print("\n== 后端启动日志（最近 30 行）==", flush=True)
        run(c, f"docker logs --tail 30 {BACKEND_CONT}", timeout=15)

        print("\n== URL 自检 ==", flush=True)
        targets = [
            ("/api/health", "200"),
            ("/api/cards?page=1&page_size=5", "200"),
            ("/api/cards/me/wallet", "401"),
            ("/api/admin/cards", "401"),
            ("/h5/cards", "308"),
            ("/h5/cards/wallet", "308"),
            ("/admin/login", "308"),
            ("/admin/product-system/cards", "308"),
        ]
        fails = []
        for path, expected in targets:
            url = f"https://localhost/autodev/{DEPLOY_ID}{path}"
            _, out, _ = run(c, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", timeout=20)
            http = (out.strip() or "000").split()[-1]
            ok_set = {"200", "204", "301", "302", "307", "308"} if expected in {"200", "308"} else {"401", "403"}
            ok = http in ok_set
            print(f"  [{http}] {path}  {'OK' if ok else 'FAIL'}", flush=True)
            if not ok:
                fails.append((path, http, expected))

        if fails:
            print(f"\n[FAIL] {len(fails)} 项失败：{fails}", flush=True)
            return 2
        print("\n== ALL OK ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
