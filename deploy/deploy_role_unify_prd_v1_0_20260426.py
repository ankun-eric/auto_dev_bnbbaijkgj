"""[2026-04-26 PRD v1.0] 商家角色统一治理 + 启停权限收紧 + 个人信息修复 部署脚本

执行步骤：
1. SSH 登录服务器
2. git pull 最新代码
3. 重建 backend / admin-web / h5-web 三端镜像（仅当本次改动相关时）
4. 启动容器并等待 healthy（启动期 main.py 会自动执行 _migrate_merchant_role_unify_v1）
5. gateway nginx reload
6. 服务器内部 curl 自检（前端首页 + admin 商家账号页 + 后端 health + profile 接口）
7. 后端容器内执行路由冲突扫描脚本，落盘 reports/route_conflicts.json
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

GIT_TOKEN = os.environ.get("GH_TOKEN", "")
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
    print(f"== SSH 连接 {USER}@{HOST}:{PORT} ==", flush=True)
    c = ssh()
    try:
        run(c, f"ls -la {PROJECT_DIR} | head -3", timeout=10)
        if not try_git_pull(c):
            print("!! git pull 失败，部署终止", flush=True)
            return 1

        print("\n== 重建 backend ==", flush=True)
        run(c, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache backend 2>&1 | tail -50", timeout=900)

        print("\n== 重建 admin-web ==", flush=True)
        run(c, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache admin-web 2>&1 | tail -60", timeout=1500)

        print("\n== 重建 h5-web ==", flush=True)
        run(c, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache h5-web 2>&1 | tail -60", timeout=1500)

        print("\n== 启动 backend + admin-web + h5-web ==", flush=True)
        run(c, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend admin-web h5-web 2>&1 | tail -30", timeout=180)

        print("\n== 等待容器 healthy ==", flush=True)
        for i in range(30):
            time.sleep(5)
            code, out, _ = run(c, f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}", timeout=10)
            lines = [ln for ln in out.splitlines() if ln.strip()]
            bad = [ln for ln in lines if "starting" in ln.lower() or "unhealthy" in ln.lower()]
            print(f"  [{i+1}/30] count={len(lines)} bad={len(bad)}", flush=True)
            if lines and not bad and any("backend" in ln for ln in lines) and any("admin" in ln for ln in lines) and any("h5" in ln for ln in lines):
                if i >= 4:
                    break

        print("\n== gateway 加入项目网络 + reload ==", flush=True)
        run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)

        print("\n== 后端容器内执行路由冲突扫描 ==", flush=True)
        run(
            c,
            f"docker exec {BACKEND_CONT} sh -c 'cd /app && python backend/scripts/scan_route_conflicts.py --json /tmp/route_conflicts.json' 2>&1 | tail -80",
            timeout=60,
        )
        run(
            c,
            f"docker exec {BACKEND_CONT} sh -c 'cat /tmp/route_conflicts.json 2>/dev/null | head -200' 2>&1 | tail -80",
            timeout=15,
        )

        print("\n== 服务器内部 curl 自检 ==", flush=True)
        for path, name in [
            ("/", "h5_root"),
            ("/merchant/login", "merchant_login_pc"),
            ("/merchant/m/login", "merchant_login_m"),
            ("/merchant/staff", "merchant_staff_pc"),
            ("/merchant/m/staff", "merchant_staff_m"),
            ("/admin/login", "admin_login"),
            ("/admin/merchant/accounts", "admin_merchant_accounts_page"),
            ("/api/health", "api_health"),
            ("/api/admin/merchant/accounts", "api_admin_merchant_accounts"),
            ("/api/merchant/profile", "api_merchant_profile"),
        ]:
            run(c, f"curl -sk -o /dev/null -w '{name}=%{{http_code}}\\n' https://localhost/autodev/{DEPLOY_ID}{path}", timeout=15)

        print("\n== 完成 ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
