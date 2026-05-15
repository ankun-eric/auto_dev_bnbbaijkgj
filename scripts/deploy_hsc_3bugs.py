#!/usr/bin/env python3
"""[BUG-FIX 2026-05-16] 健康自查 3 Bug 修复部署脚本

修复点：
- Bug 1: H5 宫格按钮 health_self_check 分支缺失
- Bug 2: 三端 (H5/小程序/Flutter) 抽屉提交 payload 字段不匹配
- Bug 3: H5 today-tasks 接口名拼写错误

部署：
1. SSH 到服务器
2. git pull 最新 master
3. 重建 backend / h5-web（仅 H5 + 后端容器需重建；小程序/Flutter 客户端独立发布）
4. HTTP 探测验证
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


def run(client, cmd: str, timeout: int = 1200):
    print(f"[ssh] $ {cmd[:140]}")
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
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        print(f"[http] error: {e}")
        return 0


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
                f"timeout 120 git fetch origin master")
            if rc == 0:
                break
            print(f"[deploy] git fetch attempt {attempt} failed, sleep 10s")
            time.sleep(10)
        run(client, f"cd {PROJECT_PATH} && git reset --hard origin/master && git log -1 --oneline")

        print("\n===== 2. docker compose build & up =====")
        # 后端 + h5 需要重建（H5 改了 page.tsx；后端无变更但确保兜底）
        rc, _, _ = run(client,
            f"cd {PROJECT_PATH} && docker compose -f docker-compose.prod.yml build h5-web backend 2>&1 | tail -40",
            timeout=1800)
        if rc != 0:
            print("[deploy] WARN: build returned non-zero")

        run(client,
            f"cd {PROJECT_PATH} && docker compose -f docker-compose.prod.yml up -d --no-deps backend h5-web 2>&1 | tail -10")

        print("\n===== 3. 等待容器健康 =====")
        time.sleep(15)
        for i in range(1, 13):
            code_h5 = http_status(BASE_URL + "/")
            code_api = http_status(BASE_URL + "/api/health")
            print(f"[probe {i}] / => {code_h5}, /api/health => {code_api}")
            if code_h5 in (200, 301, 302) and code_api == 200:
                break
            time.sleep(5)

        print("\n===== 4. 验证 today-todos 接口 =====")
        # 不带 token 应返回 401，而非 404（确认接口路由正确）
        code = http_status(BASE_URL + "/api/health-plan/today-todos")
        print(f"  GET /api/health-plan/today-todos (no auth) => {code} (期望 401, 不期望 404)")
        if code == 404:
            print("[FAIL] /api/health-plan/today-todos 返回 404，接口未就绪")
            return 3

        # 验证 health-self-check 路由也存在（应 401 而非 404）
        code_hsc = http_status(BASE_URL + "/api/health-self-check/dict")
        print(f"  GET /api/health-self-check/dict (no auth) => {code_hsc} (期望 200/401)")

        print("\n===== 5. 容器状态 =====")
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        print("\n[deploy] DONE")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
