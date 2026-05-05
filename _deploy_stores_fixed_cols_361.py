#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[361] 部署 PRD｜门店管理列表 - 固定列优化 v1.0
- 服务器：newbb.test.bangbangvip.com（ubuntu / Newbang888）
- DEPLOY_ID：6b099ed3-7175-4a78-91f4-44570c84ed27
- 项目基础URL：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27
- 改动范围：仅 admin-web 一个 .tsx 文件，4 处改动
- 部署策略：git pull → 仅 build/up admin-web 容器 → 验证页面可达
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

LOG_PATH = "_deploy_stores_fixed_cols_361.log"


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
    log("[361] 部署门店管理列表 - 固定列优化")
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
        code, _, _ = run(cli, c, timeout=120)
        if code != 0:
            log(f"  ! 命令失败：{c}")

    # 验证 page.tsx 含 fixed: 'left'/'right' 字样
    log("\n--- 阶段 2：源代码改动确认 ---")
    run(cli, f"grep -n \"fixed: 'left'\\|fixed: 'right'\" {PROJECT_DIR}/admin-web/src/app/'(admin)'/merchant/stores/page.tsx || true")

    log("\n--- 阶段 3：仅重建 admin-web 容器 ---")
    # 停旧 admin
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml stop admin-web 2>/dev/null || true", timeout=60)
    # build
    log("  构建 admin-web 镜像 ...")
    code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -120", timeout=900)
    if code != 0:
        log("  常规构建失败，尝试 --no-cache ...")
        code, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1 | tail -200", timeout=1500, check=True)
    # up（仅 admin-web，会重新创建容器）
    log("  启动 admin-web 容器 ...")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web", timeout=180, check=True)

    # 等待 healthy/up
    log("  等待 admin-web 容器 Up ...")
    for i in range(20):
        time.sleep(3)
        code, out, _ = run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}-admin", quiet=True)
        log(f"  [{i+1}/20] {out.strip()}")
        if "Up" in out:
            break

    log("\n--- 阶段 4：gateway 路由网络确认 ---")
    code, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -i gateway || true", quiet=True)
    gw_name = (out.strip().splitlines() or [""])[0]
    log(f"  gateway 容器: {gw_name or '(未找到)'}")
    if gw_name:
        run(cli, f"docker network connect {DEPLOY_ID}-network {gw_name} 2>/dev/null || true", quiet=True)
        # reload nginx 以刷新可能的 upstream 缓存
        run(cli, f"docker exec {gw_name} nginx -t 2>&1")
        run(cli, f"docker exec {gw_name} nginx -s reload 2>&1 || true")

    log("\n--- 阶段 5：HTTP 可达性验证 ---")
    # 验证管理后台门店列表页（HTML 入口）
    targets = [
        f"{BASE_URL}/admin/merchant/stores",
        f"{BASE_URL}/admin/",
        f"{BASE_URL}/api/openapi.json",
    ]
    for t in targets:
        run(cli, f"curl -sI '{t}' --max-time 10 -o /dev/null -w 'http_code=%{{http_code}}  {t}\\n'")

    # 容器日志
    log("\n--- 阶段 6：容器日志快照 ---")
    run(cli, f"docker logs --tail=30 {DEPLOY_ID}-admin 2>&1 | tail -40", timeout=30)

    log("\n" + "=" * 70)
    log("[361] 部署完成")
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
