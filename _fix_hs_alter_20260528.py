"""[BUGFIX HS-V2-ALTER 2026-05-28] 为 home_safety_callback_log / config 表补齐缺失字段。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
DB_NAME = "bini_health"
DB_PWD = "bini_health_2026"

ALTERS = [
    ("home_safety_callback_log", "request_method",        "VARCHAR(8) NULL"),
    ("home_safety_callback_log", "request_url",           "VARCHAR(512) NULL"),
    ("home_safety_callback_log", "response_status",       "INT NULL"),
    ("home_safety_callback_log", "response_body",         "TEXT NULL"),
    ("home_safety_callback_log", "processed_at",          "DATETIME NULL"),
    ("home_safety_callback_log", "device_sn",             "VARCHAR(128) NULL"),
    ("home_safety_callback_config", "last_push_judge_basis", "TEXT NULL"),
]

def docker_mysql(ssh, sql):
    cmd = f'docker exec {DB_CONTAINER} mysql -uroot -p{DB_PWD} {DB_NAME} -e "{sql}" 2>&1'
    _, o, _ = ssh.exec_command(cmd, timeout=20)
    return o.read().decode("utf-8", errors="replace")

def col_exists(ssh, table, col):
    sql = (f"SELECT COUNT(*) FROM information_schema.COLUMNS "
           f"WHERE TABLE_SCHEMA='{DB_NAME}' AND TABLE_NAME='{table}' AND COLUMN_NAME='{col}';")
    out = docker_mysql(ssh, sql)
    # 输出形如  "COUNT(*)\n1\n"
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line) > 0
    return False

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=30)

    print("=== 1) 检查表存在性 ===")
    for tbl in ("home_safety_callback_log", "home_safety_callback_config"):
        out = docker_mysql(ssh, f"SHOW TABLES LIKE '{tbl}';")
        print(f"  {tbl}: {out.strip() or '(空-表不存在!)'}")

    print("\n=== 2) 检查 ORM 期望的字段是否存在 ===")
    plan = []
    for tbl, col, type_ in ALTERS:
        exists = col_exists(ssh, tbl, col)
        flag = "OK 已存在" if exists else "MISSING 需要补"
        print(f"  {tbl}.{col}: {flag}")
        if not exists:
            plan.append((tbl, col, type_))

    if not plan:
        print("\n[完成] 所有字段已存在，无需 ALTER。")
        ssh.close()
        return

    print(f"\n=== 3) 执行 {len(plan)} 条 ALTER ===")
    for tbl, col, type_ in plan:
        sql = f"ALTER TABLE {tbl} ADD COLUMN {col} {type_};"
        out = docker_mysql(ssh, sql)
        print(f"  + {tbl}.{col} -> {out.strip() or 'OK'}")

    print("\n=== 4) 二次校验 ===")
    all_ok = True
    for tbl, col, _ in ALTERS:
        ok = col_exists(ssh, tbl, col)
        print(f"  {tbl}.{col}: {'OK' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    print("\n=== 5) DESCRIBE home_safety_callback_log ===")
    print(docker_mysql(ssh, "DESCRIBE home_safety_callback_log;"))

    print("=== 6) DESCRIBE home_safety_callback_config ===")
    print(docker_mysql(ssh, "DESCRIBE home_safety_callback_config;"))

    print("\n=== 7) 重启 backend 容器（避免 ORM 缓存）===")
    _, o, _ = ssh.exec_command(
        f"cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose restart backend 2>&1 | tail -5",
        timeout=120,
    )
    print(o.read().decode("utf-8", errors="replace"))

    ssh.close()
    print(f"\n[结果] {'ALL OK' if all_ok else 'PARTIAL FAIL'}")

if __name__ == "__main__":
    main()
