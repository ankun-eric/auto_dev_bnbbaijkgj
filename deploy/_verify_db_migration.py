#!/usr/bin/env python3
"""Verify DB migration directly."""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def sh(cmd):
    print(f">>> {cmd[:160]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(f"[stderr] {err.strip()[:300]}")
    return out

# 1. 列出容器找到 db 的真实名称
sh(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Image}}}}' | grep {PROJECT_ID}")

# 2. 直接进 db 容器查询（按 docker-compose service 名 'db'）
DB_CONTAINER = f"{PROJECT_ID}-db"

# 查表结构
sh(f"docker exec {DB_CONTAINER} sh -c 'mysql -uroot -p123456 -B -e \"DESC bini_health.chat_function_buttons;\" 2>&1' | head -30")

# 查 icon 字段数据
sh(f"docker exec {DB_CONTAINER} sh -c 'mysql -uroot -p123456 -N -B -e \"SELECT id, name, icon, icon_url FROM bini_health.chat_function_buttons LIMIT 20;\" 2>&1'")

# 统计 icon 非空数量
sh(f"docker exec {DB_CONTAINER} sh -c 'mysql -uroot -p123456 -N -B -e \"SELECT COUNT(*) total, SUM(CASE WHEN icon IS NULL OR icon=\\\"\\\" THEN 1 ELSE 0 END) empty_icon FROM bini_health.chat_function_buttons;\" 2>&1'")

# 查 app_settings 的 ai_home_config
sh(f"docker exec {DB_CONTAINER} sh -c 'mysql -uroot -p123456 -B -e \"SELECT setting_key, LEFT(setting_value, 800) FROM bini_health.app_settings WHERE setting_key=\\\"ai_home_config\\\";\" 2>&1' | head -10")

ssh.close()
