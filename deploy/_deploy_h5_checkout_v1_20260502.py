# -*- coding: utf-8 -*-
"""[2026-05-02 H5 下单流程优化 PRD v1.0] 远程部署 + URL 健康检查

复用项目现有目录结构 /home/ubuntu/{DEPLOY_ID}，使用 docker-compose.prod.yml。
"""
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
NETWORK = f"{DEPLOY_ID}-network"
GATEWAY = "gateway"
COMPOSE_FILE = "docker-compose.prod.yml"
BACKEND_CONT = f"{DEPLOY_ID}-backend"

GIT_TOKEN = os.environ.get("GIT_TOKEN") or os.environ.get("GH_TOKEN", "")
GIT_URL_TOKEN = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN
    else "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    t = c.get_transport()
    if t is not None:
        t.set_keepalive(30)
    return c


def run(c, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:], flush=True)
    if err.strip():
        print("stderr:", err[-2500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def try_git_pull(c) -> bool:
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL_TOKEN}", timeout=15)
    run(c, "git config --global http.lowSpeedLimit 1000 && git config --global http.lowSpeedTime 60", timeout=10)
    for attempt in range(1, 4):
        print(f"\n--- git fetch attempt {attempt}/3 ---", flush=True)
        run(c, f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 300 git fetch --depth=50 origin master", timeout=360)
        code, out, _ = run(c, f"cd {PROJECT_DIR} && git log -1 origin/master --oneline 2>&1 || true", timeout=10)
        if "fatal" not in out.lower() and out.strip():
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git clean -fd", timeout=20)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(5)
    return False


def main() -> int:
    print(f"== SSH {USER}@{HOST}:{PORT} ==", flush=True)
    c = ssh()
    try:
        run(c, f"ls -la {PROJECT_DIR} | head -3", timeout=10)
        if not try_git_pull(c):
            print("!! git pull 失败，部署终止", flush=True)
            return 1

        print("\n== 重建 backend ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build backend 2>&1 | tail -40",
            timeout=900)

        print("\n== 重建 h5-web ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build h5-web 2>&1 | tail -40",
            timeout=1500)

        print("\n== 重建 admin-web ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build admin-web 2>&1 | tail -40",
            timeout=1500)

        print("\n== up -d ==", flush=True)
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend admin-web h5-web 2>&1 | tail -20",
            timeout=180)

        print("\n== 等待容器 ==", flush=True)
        for i in range(30):
            time.sleep(5)
            code, out, _ = run(c, f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}", timeout=10)
            lines = [ln for ln in out.splitlines() if ln.strip()]
            ok = (lines
                  and any("backend" in ln for ln in lines)
                  and any("admin" in ln for ln in lines)
                  and any("h5" in ln for ln in lines)
                  and not any("starting" in ln.lower() or "unhealthy" in ln.lower() for ln in lines))
            print(f"  [{i+1}/30] count={len(lines)} ok={ok}", flush=True)
            if ok and i >= 3:
                break

        print("\n== gateway reload ==", flush=True)
        run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)

        print("\n== 后端启动日志（最近）==", flush=True)
        run(c, f"docker logs --tail 60 {BACKEND_CONT}", timeout=15)

        print("\n== URL 自检 ==", flush=True)
        targets = [
            ("/api/health", "api_health"),
            ("/api/products?status=active&page=1&size=3", "api_products"),
            ("/h5/login", "h5_login"),
            ("/h5/checkout", "h5_checkout"),
            ("/admin/login", "admin_login"),
            ("/admin/merchant/stores", "admin_stores"),
        ]
        fails = []
        for path, name in targets:
            url = f"https://localhost/autodev/{DEPLOY_ID}{path}"
            code, out, _ = run(c, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", timeout=20)
            http = (out.strip() or "000").split()[-1]
            ok = http in {"200", "204", "301", "302", "307", "308"}
            print(f"  [{http}] {name} {url} {'OK' if ok else 'FAIL'}", flush=True)
            if not ok:
                fails.append((name, http))

        print("\n== 新接口冒烟（无token情况下应 401/403, 不应 404/500）==", flush=True)
        for path, name in [
            ("/api/h5/checkout/init?productId=1", "h5_checkout_init"),
            ("/api/h5/slots?storeId=1&date=2026-05-03&productId=1", "h5_slots"),
        ]:
            url = f"https://localhost/autodev/{DEPLOY_ID}{path}"
            code, out, _ = run(c, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", timeout=20)
            http = (out.strip() or "000").split()[-1]
            ok = http not in {"000", "404", "500", "502", "503"}
            print(f"  [{http}] {name} {'OK' if ok else 'FAIL'}", flush=True)
            if not ok:
                fails.append((name, http))

        if fails:
            print(f"\n[FAIL] {len(fails)} 项失败：{fails}", flush=True)
            return 2

        print("\n== ALL OK ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
