#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[364] 通过 SCP 直接上传源文件部署（绕过 GitHub 国内网络问题）
"""
import sys, time, os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

LOG_PATH = "_scp_deploy_dashboard_grid9_364.log"


def log(msg):
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


def upload(cli, local_path, remote_path):
    log(f"  ↑ {local_path} -> {remote_path}")
    sftp = cli.open_sftp()
    # 确保目标目录存在
    remote_dir = "/".join(remote_path.split("/")[:-1])
    run(cli, f"mkdir -p {remote_dir}", quiet=True)
    sftp.put(local_path, remote_path)
    sftp.close()


def main():
    open(LOG_PATH, "w", encoding="utf-8").close()
    log("[364-scp] connect")
    cli = connect()

    files = [
        ("admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx",
         f"{PROJECT_DIR}/admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx"),
        ("backend/app/api/merchant_dashboard.py",
         f"{PROJECT_DIR}/backend/app/api/merchant_dashboard.py"),
        ("backend/tests/test_merchant_dashboard_grid9.py",
         f"{PROJECT_DIR}/backend/tests/test_merchant_dashboard_grid9.py"),
    ]

    log("\n--- 上传文件 ---")
    for local, remote in files:
        upload(cli, local, remote)

    log("\n--- 改动确认 ---")
    run(cli, f"grep -c '商菜单（预约看板）' {PROJECT_DIR}/admin-web/src/app/'(admin)'/product-system/orders/dashboard/page.tsx")
    run(cli, f"grep -c '_status_code' {PROJECT_DIR}/backend/app/api/merchant_dashboard.py")

    log("\n--- 重建 backend (build + force recreate) ---")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -10", timeout=900)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend", timeout=180)

    log("\n--- 重建 admin-web ---")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -10", timeout=1500)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate admin-web", timeout=180)

    log("\n--- 等待容器 Up ---")
    time.sleep(10)
    run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}")

    log("\n--- 验证容器内代码版本 ---")
    run(cli, f"docker exec {DEPLOY_ID}-backend grep -c '_status_code' /app/app/api/merchant_dashboard.py")
    run(cli, f"docker exec {DEPLOY_ID}-admin grep -c '商菜单（预约看板）' /app/.next/server/app/'(admin)'/product-system/orders/dashboard/page.js 2>/dev/null || echo 'check standalone'")

    log("\n--- gateway reload ---")
    run(cli, "docker exec gateway nginx -s reload 2>&1 || true")

    log("\n--- HTTP 验证 ---")
    targets = [
        f"{BASE_URL}/admin/product-system/orders/dashboard",
        f"{BASE_URL}/admin/product-system/orders/dashboard/",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
        f"{BASE_URL}/api/openapi.json",
    ]
    for t in targets:
        run(cli, f"curl -sI '{t}' --max-time 10 -o /dev/null -w 'http_code=%{{http_code}}  {t}\\n'")

    log("\n--- 查看 admin-web 容器日志 ---")
    run(cli, f"docker logs --tail=30 {DEPLOY_ID}-admin 2>&1 | tail -35", timeout=30)
    run(cli, f"docker logs --tail=15 {DEPLOY_ID}-backend 2>&1 | tail -20", timeout=30)

    log("\n[364-scp] done")
    cli.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"!! err: {e}")
        import traceback; log(traceback.format_exc())
        sys.exit(1)
