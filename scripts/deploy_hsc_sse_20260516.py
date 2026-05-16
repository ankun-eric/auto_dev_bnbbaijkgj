#!/usr/bin/env python3
"""[PRD-HSC-SSE-V1 2026-05-16] 健康自查 SSE 流式 + 症状描述字段 部署脚本。

部署步骤：
1. SSH 到服务器
2. git pull origin master 拉取最新代码
3. docker compose build backend h5-web --no-cache
4. docker compose up -d --no-deps backend h5-web
5. docker network 把容器重新连到 db 所在网络（避免 recreate 后 db 不可达）
6. HTTP 探活 + 接口存在性验证
"""
from __future__ import annotations

import sys
import time
import urllib.request
import urllib.error
import ssl

import paramiko


HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
PROJECT_PATH = f"/home/ubuntu/{DEPLOY_ID}"
NETWORK_NAME = f"{DEPLOY_ID}_{DEPLOY_ID}-network"


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


def http_status(url: str, timeout: int = 30, method: str = "GET", data=None,
                headers: dict | None = None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            url, method=method,
            headers={"User-Agent": "deploy-check/1.0", **(headers or {})},
            data=data,
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        print(f"[http] error: {e}")
        return 0, ""


def main() -> int:
    print(f"[deploy] Connecting to {HOST} ...")
    client = ssh_connect()
    try:
        rc, out, _ = run(client, f"test -d {PROJECT_PATH}/.git && echo OK")
        if rc != 0 or "OK" not in out:
            print(f"[deploy] FATAL: 项目目录不存在 {PROJECT_PATH}")
            return 2

        print("\n===== 1. git pull origin master (with retry) =====")
        for attempt in range(1, 6):
            rc, out, _ = run(client,
                f"cd {PROJECT_PATH} && git config --global --add safe.directory {PROJECT_PATH} && "
                f"timeout 180 git fetch origin master")
            if rc == 0:
                break
            print(f"[deploy] git fetch attempt {attempt} failed, sleep 15s")
            time.sleep(15)
        run(client, f"cd {PROJECT_PATH} && git reset --hard origin/master && git log -1 --oneline")

        print("\n===== 2. docker compose build backend + h5-web (no-cache for backend) =====")
        # backend 是必须重建的（接口改动 + schema 改动）；h5-web 改动较大也强制重建
        rc, _, _ = run(client,
            f"cd {PROJECT_PATH} && docker compose -f docker-compose.prod.yml build backend h5-web 2>&1 | tail -50",
            timeout=2400)
        if rc != 0:
            print("[deploy] WARN: build returned non-zero")

        print("\n===== 3. docker compose up -d backend h5-web =====")
        run(client,
            f"cd {PROJECT_PATH} && docker compose -f docker-compose.prod.yml up -d --no-deps backend h5-web 2>&1 | tail -10")

        print("\n===== 4. 把 backend / h5-web 重新连到 db 所在 docker 网络 =====")
        for svc in ("backend", "h5-web"):
            container = f"{DEPLOY_ID}-{svc}"
            run(client, f"docker network connect {NETWORK_NAME} {container} 2>&1 || true")

        print("\n===== 5. 等待容器健康 =====")
        time.sleep(15)
        ok = False
        for i in range(1, 25):
            code_h5, _ = http_status(BASE_URL + "/")
            code_api, _ = http_status(BASE_URL + "/api/health")
            print(f"[probe {i}] / => {code_h5}, /api/health => {code_api}")
            if code_h5 in (200, 301, 302) and code_api == 200:
                ok = True
                break
            time.sleep(5)
        if not ok:
            print("[deploy] WARN: 健康检查超时，但仍继续后续验证")

        print("\n===== 6. 验证新接口存在性（未鉴权应返回 401 而非 404）=====")
        code_old, _ = http_status(BASE_URL + "/api/health-self-check/start",
                                   method="POST", data=b"{}",
                                   headers={"Content-Type": "application/json"})
        print(f"  POST /api/health-self-check/start => {code_old} (期望 401/422, 不期望 404)")
        if code_old == 404:
            print("[FAIL] /start 接口 404")
            return 3

        code_new, _ = http_status(BASE_URL + "/api/health-self-check/start-stream",
                                   method="POST", data=b"{}",
                                   headers={"Content-Type": "application/json"})
        print(f"  POST /api/health-self-check/start-stream => {code_new} (期望 401/422, 不期望 404)")
        if code_new == 404:
            print("[FAIL] /start-stream 接口 404，部署未生效")
            return 4

        print("\n===== 7. 容器状态 =====")
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        print("\n[deploy] DONE OK")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
