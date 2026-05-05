#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[364] 部署「商家端商菜单 9 宫格改造 v1.0」
- 改动：admin-web 1 个 .tsx + backend 1 个 .py + 1 个测试文件
- 部署：git pull → 重建 admin-web 与 backend 容器 → 验证页面 + API
"""
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

import os as _os
GIT_USER = _os.environ.get("GIT_USER", "ankun-eric")
GIT_TOKEN = _os.environ.get("GIT_TOKEN", "")
GIT_REPO = "github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

LOG_PATH = "_deploy_dashboard_grid9_364.log"


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def connect():
    log(f"SSH 连接 {USER}@{HOST}:{PORT} ...")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30,
                look_for_keys=False, allow_agent=False)
    log("SSH 连接成功")
    return cli


def run(cli, cmd, timeout=180, check=False, quiet=False):
    if not quiet:
        head = cmd if len(cmd) < 240 else cmd[:240] + "...(trunc)"
        log(f"$ {head}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            tail = out if len(out) < 4000 else out[-4000:]
            log(f"  ↳ stdout:\n{tail}")
        if err.strip():
            tail = err if len(err) < 4000 else err[-4000:]
            log(f"  ↳ stderr:\n{tail}")
        log(f"  ↳ exit={code}")
    if check and code != 0:
        raise RuntimeError(f"命令失败 exit={code}: {cmd}")
    return code, out, err


def main():
    open(LOG_PATH, "w", encoding="utf-8").close()
    log("=" * 70)
    log("[364] 部署 商家端商菜单 9 宫格改造")
    log("=" * 70)

    cli = connect()

    log("\n--- 阶段 1：拉取最新代码 ---")
    cmds = [
        f"cd {PROJECT_DIR} && git remote set-url origin https://{GIT_USER}:{GIT_TOKEN}@{GIT_REPO}",
        f"cd {PROJECT_DIR} && timeout 90 git fetch origin master --no-tags",
        f"cd {PROJECT_DIR} && git reset --hard origin/master",
        f"cd {PROJECT_DIR} && git log -1 --oneline",
    ]
    for c in cmds:
        run(cli, c, timeout=120)

    # 选择 compose 文件
    log("\n--- 阶段 2：选择 docker-compose 文件 ---")
    code, out, _ = run(cli, f"ls {PROJECT_DIR}/docker-compose*.yml")
    compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"
    log(f"  使用 compose 文件: {compose_file}")

    log("\n--- 阶段 3：源代码改动确认 ---")
    run(cli, f"grep -n '商菜单\\|9 宫格改造' {PROJECT_DIR}/admin-web/src/app/'(admin)'/product-system/orders/dashboard/page.tsx | head -5 || true")
    run(cli, f"grep -n '_status_code\\|aggregate_status_code' {PROJECT_DIR}/backend/app/api/merchant_dashboard.py | head -5 || true")

    log("\n--- 阶段 4：重建 backend 容器（API 改动） ---")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} stop backend 2>/dev/null || true", timeout=60)
    code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} build backend 2>&1 | tail -100", timeout=900)
    if code != 0:
        log("  常规构建失败，尝试 --no-cache ...")
        run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} build --no-cache backend 2>&1 | tail -150", timeout=1500, check=True)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} up -d backend", timeout=180, check=True)

    log("  等待 backend 容器 Up ...")
    for i in range(20):
        time.sleep(3)
        code, out, _ = run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}-backend", quiet=True)
        log(f"  [{i+1}/20] {out.strip()}")
        if "Up" in out:
            break

    log("\n--- 阶段 5：重建 admin-web 容器 ---")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} stop admin-web 2>/dev/null || true", timeout=60)
    code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} build admin-web 2>&1 | tail -120", timeout=900)
    if code != 0:
        log("  常规构建失败，尝试 --no-cache ...")
        run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} build --no-cache admin-web 2>&1 | tail -200", timeout=1500, check=True)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f {compose_file} up -d admin-web", timeout=180, check=True)

    log("  等待 admin-web 容器 Up ...")
    for i in range(20):
        time.sleep(3)
        code, out, _ = run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}-admin", quiet=True)
        log(f"  [{i+1}/20] {out.strip()}")
        if "Up" in out:
            break

    log("\n--- 阶段 6：gateway 路由确认 ---")
    code, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -i gateway || true", quiet=True)
    gw_name = (out.strip().splitlines() or [""])[0]
    log(f"  gateway 容器: {gw_name or '(未找到)'}")
    if gw_name:
        run(cli, f"docker network connect {DEPLOY_ID}-network {gw_name} 2>/dev/null || true", quiet=True)
        run(cli, f"docker exec {gw_name} nginx -t 2>&1")
        run(cli, f"docker exec {gw_name} nginx -s reload 2>&1 || true")

    log("\n--- 阶段 7：HTTP 可达性验证 ---")
    targets = [
        f"{BASE_URL}/admin/product-system/orders/dashboard",
        f"{BASE_URL}/admin/product-system/orders",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
        f"{BASE_URL}/api/openapi.json",
    ]
    for t in targets:
        run(cli, f"curl -sI '{t}' --max-time 10 -o /dev/null -w 'http_code=%{{http_code}}  {t}\\n'")

    # API JSON snapshot（time-slots 是公开的）
    log("\n--- 阶段 8：time-slots 接口 JSON 验证 ---")
    run(cli, f"curl -s --max-time 15 '{BASE_URL}/api/merchant/dashboard/time-slots' | head -c 500 ; echo")

    log("\n--- 阶段 9：容器日志快照 ---")
    run(cli, f"docker logs --tail=20 {DEPLOY_ID}-backend 2>&1 | tail -25", timeout=30)
    run(cli, f"docker logs --tail=20 {DEPLOY_ID}-admin 2>&1 | tail -25", timeout=30)

    log("\n" + "=" * 70)
    log("[364] 部署完成")
    log("=" * 70)
    cli.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"!! 异常: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
