# -*- coding: utf-8 -*-
"""[2026-05-02 卡功能 v1.1 第 1 期] 重新部署 v2：使用 git pull rebase 替代浅拉取，避免 grafted 边界问题。"""
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
    # 先尝试解开浅拉取（如果是 shallow clone）
    run(c, f"cd {PROJECT_DIR} && (test -f .git/shallow && git fetch --unshallow 2>&1 || echo 'not shallow')",
        timeout=300)

    for attempt in range(1, 9):
        print(f"\n--- git fetch attempt {attempt}/8 ---", flush=True)
        # 不限制 depth，强制全部 fetch
        run(c,
            f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 240 "
            f"git -c http.postBuffer=524288000 fetch origin master 2>&1",
            timeout=300)
        _, out, _ = run(c,
            f"cd {PROJECT_DIR} && git log -1 origin/master --format=%h",
            timeout=10)
        head = out.strip().split()[-1] if out.strip() else ""
        print(f"  origin/master HEAD = {head}, expected starts with {EXPECTED_COMMIT}", flush=True)
        if head.startswith(EXPECTED_COMMIT):
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(8)
    return False


def main() -> int:
    c = ssh()
    try:
        if not fetch_until_latest(c):
            print("!! 8 次 fetch 失败，尝试 fallback：直接 git clone 一份新的、覆盖回去", flush=True)
            # 极端兜底：克隆到临时目录，然后只拷贝代码（保留 .git）
            run(c, f"cd /tmp && rm -rf bini_health_fresh && timeout 300 git clone --depth=20 {GIT_URL_TOKEN} bini_health_fresh", timeout=360)
            _, out, _ = run(c, "cd /tmp/bini_health_fresh && git log -1 --format=%h", timeout=10)
            head = out.strip().split()[-1] if out.strip() else ""
            if not head.startswith(EXPECTED_COMMIT):
                print(f"!! fallback 也失败（{head}），部署终止", flush=True)
                return 1
            # 用 rsync 覆盖文件（保留 .git）
            run(c, f"rsync -a --delete --exclude '.git' /tmp/bini_health_fresh/ {PROJECT_DIR}/", timeout=120)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)

        print("\n== 重建 backend ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build backend 2>&1 | tail -15",
            timeout=900)

        print("\n== 重建 h5-web ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build h5-web 2>&1 | tail -15",
            timeout=1500)

        print("\n== 重建 admin-web ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build admin-web 2>&1 | tail -15",
            timeout=1500)

        print("\n== up -d ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend admin-web h5-web 2>&1 | tail -15",
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

        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1 || true", timeout=15)

        print("\n== 后端启动日志 ==", flush=True)
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
            if expected == "200":
                ok = http in {"200", "204"}
            elif expected == "308":
                ok = http in {"200", "204", "301", "302", "307", "308"}
            else:  # "401"
                ok = http in {"401", "403"}
            print(f"  [{http}] {path}  expect {expected}  {'OK' if ok else 'FAIL'}", flush=True)
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
