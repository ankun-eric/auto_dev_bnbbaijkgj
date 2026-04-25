"""[2026-04-25] PRD V1.0 商家个人信息回填修复 + H5 店铺信息编辑能力开放

部署步骤：
1. SSH 登录服务器
2. git pull 远程仓库（重试 3 次）
3. 重建 backend + h5-web 镜像（这次同时改了后端和前端）
4. 启动容器，等待 healthy
5. gateway 重连项目网络 + reload
6. 内部 curl 自检
"""
from __future__ import annotations

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
import os as _os

GIT_TOKEN = _os.environ.get("GH_TOKEN", "REDACTED")
GIT_URL_TOKEN = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)
EXPECTED_COMMIT = "8718c20"


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    transport = c.get_transport()
    if transport is not None:
        transport.set_keepalive(30)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    print(f"\n$ {cmd}", flush=True)
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:], flush=True)
    if err.strip():
        print("stderr:", err[-2500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def try_git_pull(c: paramiko.SSHClient) -> bool:
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL_TOKEN}", timeout=15)
    run(c, "git config --global http.lowSpeedLimit 1000 && git config --global http.lowSpeedTime 60", timeout=10)
    for attempt in range(1, 4):
        print(f"\n--- git fetch attempt {attempt}/3 ---", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 300 "
            f"git fetch --depth=50 origin master",
            timeout=360,
        )
        code, out, _ = run(
            c,
            f"cd {PROJECT_DIR} && git log -1 origin/master --oneline 2>&1 || true",
            timeout=10,
        )
        if EXPECTED_COMMIT in out:
            print(f"  ✓ origin/master 已包含 {EXPECTED_COMMIT}", flush=True)
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git clean -fd", timeout=20)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(5)
    return False


def main() -> int:
    print(f"== SSH 连接 {USER}@{HOST}:{PORT} ==", flush=True)
    c = ssh()
    try:
        run(c, f"ls -la {PROJECT_DIR} | head -3", timeout=10)

        if not try_git_pull(c):
            print("!! git pull 失败，部署终止", flush=True)
            return 1

        print("\n== 重建 backend ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache backend 2>&1 | tail -50",
            timeout=900,
        )

        print("\n== 重建 h5-web ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache h5-web 2>&1 | tail -60",
            timeout=1500,
        )

        print("\n== 启动 backend + h5-web ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend h5-web 2>&1 | tail -30",
            timeout=180,
        )

        print("\n== 等待容器 healthy ==", flush=True)
        for i in range(24):
            time.sleep(5)
            code, out, _ = run(
                c,
                f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}",
                timeout=10,
            )
            lines = [ln for ln in out.splitlines() if ln.strip()]
            bad = [ln for ln in lines if "starting" in ln.lower() or "unhealthy" in ln.lower()]
            print(f"  [{i+1}/24] count={len(lines)} bad={len(bad)}", flush=True)
            if lines and not bad and any("backend" in ln for ln in lines) and any("h5" in ln for ln in lines):
                if i >= 5:
                    break

        print("\n== gateway 加入项目网络 + reload ==", flush=True)
        run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
        run(c, f"docker network inspect {NETWORK} --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'", timeout=10)
        run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)

        print("\n== 服务器内部 curl 自检 ==", flush=True)
        for path, name in [
            ("/", "h5_root"),
            ("/login", "login"),
            ("/merchant/login", "merchant_pc_login"),
            ("/merchant/profile", "merchant_pc_profile"),
            ("/merchant/store-settings", "merchant_pc_store"),
            ("/merchant/m/profile", "merchant_h5_profile"),
            ("/merchant/m/store-settings", "merchant_h5_store"),
            ("/merchant/m/me", "merchant_h5_me"),
            ("/api/health", "api_health"),
            ("/api/merchant/profile", "api_merchant_profile"),
            ("/api/merchant/shop/info", "api_merchant_shop"),
        ]:
            run(
                c,
                f"curl -sk -o /dev/null -w '{name}=%{{http_code}}\\n' "
                f"https://localhost/autodev/{DEPLOY_ID}{path}",
                timeout=15,
            )

        print("\n== 完成 ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
