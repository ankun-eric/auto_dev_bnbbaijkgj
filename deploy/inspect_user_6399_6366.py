"""[2026-04-26] 查询 6399、6366 当前数据状态、定位 db 容器名。"""
from __future__ import annotations
import sys
import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DB_PASS = "bini_health_2026"


def run(c, cmd, timeout=60):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out, flush=True)
    if err.strip():
        print("ERR:", err, flush=True)
    return code, out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASS, timeout=30)
    try:
        # 1. 找 db 容器
        run(c, f"docker ps --format '{{{{.Names}}}}' | grep -i {DEPLOY_ID}")
        # 2. 进 db 容器看下 mysql 客户端
        DB_CONT = f"{DEPLOY_ID}-db"
        run(c, f"docker exec {DB_CONT} sh -c 'echo OK; ls /var/lib/mysql 2>&1 | head -3' 2>&1 | head -10")
        # 2.b 看 docker-compose 中 db 的密码
        run(c, f"grep -iE 'mysql_root_password|mysql_password|database_url|MYSQL_' /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml | head -30")
        run(c, f"docker exec {DB_CONT} env | grep -i mysql | head -20")
        def mysql(sql, head=80):
            quoted = sql.replace('"', '\\"')
            return run(c, f'docker exec {DB_CONT} sh -c "mysql -uroot -p{DB_PASS} bini_health -e \\"{quoted}\\""' + f" 2>&1 | head -{head}")

        # 3. 找出 6399、6366 对应的 user 行
        mysql(
            "SELECT id, phone, nickname, role, status FROM users "
            "WHERE phone LIKE '%6399%' OR phone LIKE '%6366%' "
            "ORDER BY id;"
        )
        # 4. membership 与 store 详情
        mysql(
            "SELECT u.id, u.phone, u.nickname, msm.id AS membership_id, msm.store_id, "
            "ms.store_name, msm.member_role, msm.role_code, msm.status "
            "FROM users u LEFT JOIN merchant_store_memberships msm ON msm.user_id = u.id "
            "LEFT JOIN merchant_stores ms ON ms.id = msm.store_id "
            "WHERE u.phone LIKE '%6399' OR u.phone LIKE '%6366' "
            "ORDER BY u.id, msm.id;"
        )
        # 5. account_identities
        mysql(
            "SELECT ai.user_id, u.phone, ai.identity_type, ai.status FROM account_identities ai "
            "JOIN users u ON u.id = ai.user_id "
            "WHERE u.phone LIKE '%6399' OR u.phone LIKE '%6366' "
            "ORDER BY ai.user_id;"
        )
        # 6. 看下整体老板/店长/核销员等账号分布（验证修复后效果）
        mysql(
            "SELECT msm.member_role, msm.role_code, COUNT(*) AS cnt "
            "FROM merchant_store_memberships msm WHERE msm.status='active' "
            "GROUP BY msm.member_role, msm.role_code ORDER BY msm.member_role;"
        )
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
