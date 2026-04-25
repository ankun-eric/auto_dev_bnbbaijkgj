"""[2026-04-26] 商家账号-角色显示错乱修复 + 员工列表抽屉一次性修复方案部署

执行步骤：
1. SSH 登录服务器
2. git pull 最新代码
3. 重建 backend + admin-web 镜像
4. 启动容器，等待 healthy
5. gateway reload
6. 数据修正：把 6399 (user_id=2) 真实角色由 store_manager/manager 改为 owner/boss
   - users.role: user -> merchant
   - merchant_store_memberships(id=1): member_role='owner', role_code='boss'
   - account_identities(user_id=2): 删除 user/merchant_staff，新增 merchant_owner
   修改前先备份原始行到日志
7. 内部 curl 自检 + 角色显示验证
"""
from __future__ import annotations
import os, sys, time
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
DB_CONT = f"{DEPLOY_ID}-db"
DB_PASS = "bini_health_2026"

# 注意：token 仅通过环境变量 GH_TOKEN 传入，不在源码中硬编码
GIT_TOKEN = os.environ.get("GH_TOKEN", "")
GIT_URL_TOKEN = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN else
    "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
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


def mysql(c, sql: str, head: int = 60) -> tuple[int, str, str]:
    q = sql.replace('"', '\\"').replace("$", "\\$")
    return run(c, f'docker exec {DB_CONT} sh -c "mysql -uroot -p{DB_PASS} bini_health -e \\"{q}\\"" 2>&1 | head -{head}', timeout=60)


def try_git_pull(c) -> bool:
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL_TOKEN}", timeout=15)
    run(c, "git config --global http.lowSpeedLimit 1000 && git config --global http.lowSpeedTime 60", timeout=10)
    for attempt in range(1, 4):
        print(f"\n--- git fetch attempt {attempt}/3 ---", flush=True)
        run(c, f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 300 git fetch --depth=50 origin master", timeout=360)
        code, out, _ = run(c, f"cd {PROJECT_DIR} && git log -1 origin/master --oneline 2>&1 || true", timeout=10)
        if "origin/master" not in out and "fatal" not in out.lower():
            # 已经有 origin/master 行
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git clean -fd", timeout=20)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        if "fatal" not in out.lower() and out.strip():
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git clean -fd", timeout=20)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(5)
    return False


def fix_db_data(c) -> None:
    print("\n========== 数据修正阶段 ==========", flush=True)

    print("\n--- 步骤 1: 修复前快照（备份） ---", flush=True)
    mysql(c, "SELECT id, phone, nickname, role, status FROM users WHERE id=2;")
    mysql(c, "SELECT id, user_id, store_id, member_role, role_code, status FROM merchant_store_memberships WHERE id=1;")
    mysql(c, "SELECT id, user_id, identity_type, status FROM account_identities WHERE user_id=2 ORDER BY id;")

    print("\n--- 步骤 2: 执行数据修正 SQL ---", flush=True)
    # 注意：MySQL 8 默认 enum 列接受字符串值
    mysql(c, "UPDATE users SET role='merchant', updated_at=NOW() WHERE id=2;")
    mysql(c, "UPDATE merchant_store_memberships SET member_role='owner', role_code='boss', updated_at=NOW() WHERE id=1;")
    mysql(c, "DELETE FROM account_identities WHERE user_id=2 AND identity_type IN ('user','merchant_staff');")
    # 用 INSERT IGNORE 防止重复
    mysql(c, "INSERT IGNORE INTO account_identities (user_id, identity_type, status, created_at, updated_at) VALUES (2,'merchant_owner','active',NOW(),NOW());")

    print("\n--- 步骤 3: 修复后核验 ---", flush=True)
    mysql(c, "SELECT id, phone, nickname, role, status FROM users WHERE id=2;")
    mysql(c, "SELECT id, user_id, store_id, member_role, role_code, status FROM merchant_store_memberships WHERE id=1;")
    mysql(c, "SELECT id, user_id, identity_type, status FROM account_identities WHERE user_id=2 ORDER BY id;")
    # 看下 6399 的 store_permissions 是否还在
    mysql(c, "SELECT membership_id, module_code FROM merchant_store_permissions WHERE membership_id=1 ORDER BY module_code;")
    # 6366 不动
    print("\n--- 步骤 4: 确认 6366 未受影响 ---", flush=True)
    mysql(c, "SELECT id, phone, role, status FROM users WHERE id=18;")
    mysql(c, "SELECT id, user_id, store_id, member_role, role_code, status FROM merchant_store_memberships WHERE user_id=18;")
    mysql(c, "SELECT user_id, identity_type, status FROM account_identities WHERE user_id=18;")


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

        print("\n== 启动 backend + admin-web ==", flush=True)
        run(c, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend admin-web 2>&1 | tail -30", timeout=180)

        print("\n== 等待容器 healthy ==", flush=True)
        for i in range(24):
            time.sleep(5)
            code, out, _ = run(c, f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}", timeout=10)
            lines = [ln for ln in out.splitlines() if ln.strip()]
            bad = [ln for ln in lines if "starting" in ln.lower() or "unhealthy" in ln.lower()]
            print(f"  [{i+1}/24] count={len(lines)} bad={len(bad)}", flush=True)
            if lines and not bad and any("backend" in ln for ln in lines) and any("admin" in ln for ln in lines):
                if i >= 4:
                    break

        print("\n== gateway 加入项目网络 + reload ==", flush=True)
        run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)

        # 数据修正（在新代码生效后执行 SQL）
        fix_db_data(c)

        print("\n== 服务器内部 curl 自检 ==", flush=True)
        for path, name in [
            ("/", "h5_root"),
            ("/admin/login", "admin_login"),
            ("/admin/merchant/accounts", "admin_merchant_accounts_page"),
            ("/api/health", "api_health"),
            ("/api/admin/merchant/accounts", "api_admin_merchant_accounts"),
            ("/api/admin/merchant/accounts/2/staff", "api_staff_2"),
        ]:
            run(c, f"curl -sk -o /dev/null -w '{name}=%{{http_code}}\\n' https://localhost/autodev/{DEPLOY_ID}{path}", timeout=15)

        print("\n== 完成 ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
