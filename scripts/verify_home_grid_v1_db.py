#!/usr/bin/env python3
"""验证服务器数据库迁移结果：chat_function_buttons.is_recommended / is_capsule 字段及数据。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DB_CONTAINER = f"{DEPLOY_ID}-db"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def sh(cmd, t=60):
    print(f"\n$ {cmd[:160]}")
    _, out, err = c.exec_command(cmd, timeout=t)
    s = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    if s.strip():
        print(s.rstrip())
    if e.strip():
        print(f"[err] {e.rstrip()}")

# 1) 看 backend 启动迁移日志
sh(f"docker logs --tail 500 {DEPLOY_ID}-backend 2>&1 | grep -E 'prd_aichat_home_grid_v1|home_grid|is_recommended|is_capsule' | tail -30")

# 2) 看表 schema
sh(f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 -Dbini_health -e \"SHOW COLUMNS FROM chat_function_buttons LIKE 'is_%'\"")

# 3) 看数据：所有按钮的 is_enabled/is_recommended/is_capsule
sh(f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 -Dbini_health -e \"SELECT id,name,is_enabled,is_recommended,is_capsule FROM chat_function_buttons ORDER BY sort_weight,id\"")

# 4) 看 app_settings 中的迁移标志
sh(f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 -Dbini_health -e \"SELECT setting_key,setting_value FROM app_settings WHERE setting_key LIKE '%_migration_done%'\"")

c.close()
