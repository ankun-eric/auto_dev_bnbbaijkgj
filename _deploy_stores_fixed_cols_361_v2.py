#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[361 v2] 部署 PRD｜门店管理列表 - 固定列优化（修正版）
- 强制重试 git fetch（GitHub 国内网络不稳定，重试 5 次，递增 sleep）
- 用 grep 确认源码改动到位
- 用 --no-cache 重建 admin-web 镜像，确保改动进镜像
- 重启 admin-web 容器并验证
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
# 严禁硬编码 token：从环境变量 GIT_TOKEN 读取（部署脚本运行前 export）
GIT_TOKEN = _os.environ.get("GIT_TOKEN", "")
GIT_REPO = "github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

EXPECTED_COMMIT_PREFIX = "4e20c17"  # 本次推送

LOG_PATH = "_deploy_stores_fixed_cols_361_v2.log"


def log(msg):
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
    log("[361 v2] 部署门店管理列表 - 固定列优化（修正版）")
    log("=" * 70)

    cli = connect()

    log("\n--- 阶段 1：拉取最新代码（重试 5 次） ---")
    run(cli, f"cd {PROJECT_DIR} && git remote set-url origin https://{GIT_USER}:{GIT_TOKEN}@{GIT_REPO}")

    fetched = False
    for i in range(5):
        log(f"  fetch 第 {i+1}/5 次")
        code, _, _ = run(cli, f"cd {PROJECT_DIR} && timeout 120 git fetch origin master --no-tags", timeout=140)
        if code == 0:
            fetched = True
            break
        sleep_s = 5 * (i + 1)
        log(f"  fetch 失败，{sleep_s}s 后重试")
        time.sleep(sleep_s)
    if not fetched:
        log("  !! fetch 重试 5 次仍失败，部署中止")
        sys.exit(2)

    run(cli, f"cd {PROJECT_DIR} && git reset --hard origin/master", check=True)
    code, out, _ = run(cli, f"cd {PROJECT_DIR} && git log -1 --oneline", quiet=True)
    log(f"  当前 HEAD: {out.strip()}")
    if EXPECTED_COMMIT_PREFIX not in out:
        log(f"  !! HEAD 不包含期望 commit 前缀 {EXPECTED_COMMIT_PREFIX}，可能 push 未到达远程")
        sys.exit(3)
    log(f"  ✓ HEAD 命中期望 commit {EXPECTED_COMMIT_PREFIX}")

    log("\n--- 阶段 2：源代码改动确认 ---")
    code, out, _ = run(cli, f"grep -n \"fixed: 'left'\\|fixed: 'right'\" {PROJECT_DIR}/admin-web/src/app/'(admin)'/merchant/stores/page.tsx")
    if code != 0 or "fixed:" not in out:
        log("  !! 未在 page.tsx 中找到 fixed:'left'/'right' 字样，部署中止")
        sys.exit(4)
    log("  ✓ 源代码改动已生效（包含 fixed:'left' 和 fixed:'right'）")

    log("\n--- 阶段 3：重建 admin-web 镜像（--no-cache） ---")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml stop admin-web 2>/dev/null || true", timeout=60)
    log("  执行 build --no-cache admin-web ...")
    code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1 | tail -200", timeout=1500, check=True)

    log("  启动 admin-web 容器 ...")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web", timeout=180, check=True)

    log("  等待 admin-web 容器 Up ...")
    for i in range(20):
        time.sleep(3)
        code, out, _ = run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}-admin", quiet=True)
        log(f"  [{i+1}/20] {out.strip()}")
        if "Up" in out:
            break

    log("\n--- 阶段 4：gateway 网络与 reload ---")
    code, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -i gateway || true", quiet=True)
    gw_name = (out.strip().splitlines() or [""])[0]
    if gw_name:
        run(cli, f"docker network connect {DEPLOY_ID}-network {gw_name} 2>/dev/null || true", quiet=True)
        run(cli, f"docker exec {gw_name} nginx -t 2>&1")
        run(cli, f"docker exec {gw_name} nginx -s reload 2>&1 || true")

    log("\n--- 阶段 5：HTTP 可达性验证 ---")
    targets = [
        f"{BASE_URL}/admin/",
        f"{BASE_URL}/admin/merchant/stores",
        f"{BASE_URL}/admin/merchant/stores/",
        f"{BASE_URL}/api/openapi.json",
    ]
    for t in targets:
        run(cli, f"curl -sI '{t}' --max-time 10 -o /dev/null -w 'http_code=%{{http_code}}  {t}\\n'")

    # 拉取页面 HTML，确认包含本次代码新增的标识（PRD 注释）
    log("\n--- 阶段 6：HTML 内容快照（页面是否能 SSR 出 store_name 列） ---")
    run(cli, f"curl -s '{BASE_URL}/admin/merchant/stores/' --max-time 15 | head -c 3000")

    log("\n--- 阶段 7：admin 容器日志 ---")
    run(cli, f"docker logs --tail=40 {DEPLOY_ID}-admin 2>&1 | tail -40", timeout=30)

    log("\n" + "=" * 70)
    log("[361 v2] 部署完成")
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
