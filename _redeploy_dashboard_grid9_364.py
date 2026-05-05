#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[364] 重新部署 - git fetch 超时重试
确保 origin/master 拉到最新 commit (5ae72e5) 后再重建容器
"""
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
import os as _os
GIT_USER = _os.environ.get("GIT_USER", "ankun-eric")
GIT_TOKEN = _os.environ.get("GIT_TOKEN", "")
GIT_REPO = "github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

LOG_PATH = "_redeploy_dashboard_grid9_364.log"


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30,
                look_for_keys=False, allow_agent=False)
    return cli


def run(cli, cmd, timeout=180, quiet=False):
    if not quiet:
        log(f"$ {cmd if len(cmd) < 240 else cmd[:240] + '...'}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip(): log(f"  ↳ {out[:2500]}")
        if err.strip(): log(f"  ↳ ERR {err[:2500]}")
        log(f"  ↳ exit={code}")
    return code, out, err


def main():
    open(LOG_PATH, "w", encoding="utf-8").close()
    log("[364-redeploy] connect")
    cli = connect()

    log("\n--- fetch 重试 ---")
    for i in range(5):
        log(f"  fetch attempt {i+1}/5")
        run(cli, f"cd {PROJECT_DIR} && timeout 180 git fetch origin master --no-tags 2>&1", timeout=240)
        code, out, _ = run(cli, f"cd {PROJECT_DIR} && git rev-parse origin/master")
        log(f"  origin/master = {out.strip()}")
        if "5ae72e5" in out or out.strip().startswith("5ae72e5"):
            log("  ✓ 已拉到最新 5ae72e5")
            break
        time.sleep(5)

    run(cli, f"cd {PROJECT_DIR} && git reset --hard origin/master")
    run(cli, f"cd {PROJECT_DIR} && git log -3 --oneline")

    log("\n--- 改动确认 ---")
    run(cli, f"grep -c '商菜单' {PROJECT_DIR}/admin-web/src/app/'(admin)'/product-system/orders/dashboard/page.tsx || true")
    run(cli, f"grep -c '_status_code' {PROJECT_DIR}/backend/app/api/merchant_dashboard.py || true")

    log("\n--- 重建 backend (no-cache for app/) ---")
    # backend 通过 COPY . . 复制源码，需要重新构建确保 merchant_dashboard.py 是最新版
    code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -40", timeout=900)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend", timeout=180)

    log("\n--- 重建 admin-web (no-cache) ---")
    code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1 | tail -50", timeout=1500)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate admin-web", timeout=180)

    log("\n--- 等待容器 Up ---")
    time.sleep(8)
    run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}")

    log("\n--- gateway reload ---")
    run(cli, "docker exec gateway nginx -s reload 2>&1 || true")

    log("\n--- HTTP 验证 ---")
    targets = [
        f"{BASE_URL}/admin/product-system/orders/dashboard",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
        f"{BASE_URL}/api/openapi.json",
    ]
    for t in targets:
        run(cli, f"curl -sI '{t}' --max-time 10 -o /dev/null -w 'http_code=%{{http_code}}  {t}\\n'")

    log("\n--- 验证容器内代码版本 ---")
    run(cli, f"docker exec {DEPLOY_ID}-backend grep -c '_status_code' /app/app/api/merchant_dashboard.py")

    log("\n[364-redeploy] done")
    cli.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"!! err: {e}")
        import traceback; log(traceback.format_exc())
        sys.exit(1)
