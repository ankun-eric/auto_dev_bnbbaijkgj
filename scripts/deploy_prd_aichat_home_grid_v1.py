#!/usr/bin/env python3
"""[PRD-AICHAT-HOME-GRID-V1 2026-05-16] AI 对话首页功能宫格与胶囊条优化 部署脚本

部署：
  1. SSH 到服务器
  2. git pull --rebase 最新 master
  3. docker compose 重建 backend + h5-web + admin-web
  4. 重启容器，等待启动迁移（is_recommended / is_capsule 字段添加 + 历史数据回填）
  5. HTTP 探活
"""
import sys
import time
import urllib.request
import ssl

import paramiko


HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
PROJECT_PATH = f"/home/ubuntu/{DEPLOY_ID}"


def ssh_connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD,
              timeout=30, allow_agent=False, look_for_keys=False)
    return c


def run(client, cmd: str, timeout: int = 1800):
    print(f"[ssh] $ {cmd[:160]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(f"[stderr] {err.rstrip()}")
    return rc, out, err


def http_status(url: str, timeout: int = 30):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "deploy-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        print(f"[http] error: {e}")
        return 0, b""


def main() -> int:
    print(f"[deploy] Connecting to {HOST} ...")
    client = ssh_connect()
    try:
        rc, out, _ = run(client, f"test -d {PROJECT_PATH}/.git && echo OK")
        if rc != 0 or "OK" not in out:
            print(f"[deploy] FATAL: 项目目录不存在 {PROJECT_PATH}")
            return 2

        print("\n===== 1. git fetch + reset to origin/master =====")
        for attempt in range(1, 6):
            rc, _, _ = run(client,
                f"cd {PROJECT_PATH} && git config --global --add safe.directory {PROJECT_PATH} && "
                f"timeout 180 git fetch origin master")
            if rc == 0:
                break
            print(f"[deploy] git fetch attempt {attempt} failed, sleep 10s")
            time.sleep(10)
        run(client, f"cd {PROJECT_PATH} && git reset --hard origin/master && git log -1 --oneline")

        print("\n===== 2. docker compose build backend + h5-web + admin-web =====")
        rc, _, _ = run(client,
            f"cd {PROJECT_PATH} && docker compose -f docker-compose.prod.yml build backend h5-web admin-web 2>&1 | tail -60",
            timeout=2400)
        if rc != 0:
            print("[deploy] WARN: build returned non-zero")

        print("\n===== 3. docker compose up -d --no-deps =====")
        run(client,
            f"cd {PROJECT_PATH} && docker compose -f docker-compose.prod.yml up -d --no-deps backend h5-web admin-web 2>&1 | tail -10")

        print("\n===== 3b. 修复网络（backend/h5/admin 接入 DB 所在 network） =====")
        DB_NETWORK = f"{DEPLOY_ID}_{DEPLOY_ID}-network"
        for svc in ("backend", "h5", "admin"):
            run(client, f"docker network disconnect {DB_NETWORK} {DEPLOY_ID}-{svc} 2>&1 || true")
            run(client, f"docker network connect {DB_NETWORK} {DEPLOY_ID}-{svc} 2>&1 || true")
        time.sleep(3)
        run(client, f"docker restart {DEPLOY_ID}-backend 2>&1 || true")
        time.sleep(8)

        print("\n===== 4. 等待容器健康 =====")
        time.sleep(15)
        for i in range(1, 24):
            code_h5, _ = http_status(BASE_URL + "/")
            code_api, _ = http_status(BASE_URL + "/api/health")
            print(f"[probe {i}] / => {code_h5}, /api/health => {code_api}")
            if code_h5 in (200, 301, 302) and code_api == 200:
                break
            time.sleep(5)

        print("\n===== 5. 查启动迁移日志 =====")
        run(client,
            f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1 | grep -E 'prd_aichat_home_grid_v1|home_grid' | tail -20")

        print("\n===== 6. 公开功能按钮接口 =====")
        code_fb, body_fb = http_status(BASE_URL + "/api/function-buttons")
        print(f"  GET /api/function-buttons => {code_fb}; size={len(body_fb)}")
        code_grid, body_grid = http_status(BASE_URL + "/api/function-buttons?position=grid")
        print(f"  GET /api/function-buttons?position=grid => {code_grid}; size={len(body_grid)}")
        code_cap, body_cap = http_status(BASE_URL + "/api/function-buttons?position=capsule")
        print(f"  GET /api/function-buttons?position=capsule => {code_cap}; size={len(body_cap)}")

        if 200 not in (code_fb, code_grid, code_cap):
            print("[deploy] FAIL: 公开功能按钮接口未全部 200")
            return 3

        # 简单校验 body 含 is_recommended/is_capsule 字段
        import json as _json
        for label, raw in [("all", body_fb), ("grid", body_grid), ("capsule", body_cap)]:
            try:
                arr = _json.loads(raw.decode("utf-8"))
                if isinstance(arr, list) and arr:
                    first = arr[0]
                    has_rec = "is_recommended" in first
                    has_cap = "is_capsule" in first
                    print(f"  [{label}] 首条按钮: id={first.get('id')} name={first.get('name')} "
                          f"is_recommended={first.get('is_recommended')} is_capsule={first.get('is_capsule')} "
                          f"hasFields={has_rec and has_cap}")
                else:
                    print(f"  [{label}] 数组为空或非 list：{type(arr)}")
            except Exception as e:
                print(f"  [{label}] 解析失败：{e}")

        print("\n===== 7. 容器状态 =====")
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        print("\n[deploy] DONE")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
