#!/usr/bin/env python3
"""Verify DB migration with correct password."""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
MYSQL_PWD = "bini_health_2026"

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

DB = f"{PROJECT_ID}-db"

# 查表结构（关注 icon 字段）
print("\n========= TABLE STRUCTURE =========")
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "DESC chat_function_buttons;"')

# 查 icon 数据
print("\n========= ICON DATA =========")
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "SELECT id, name, icon, LEFT(icon_url, 30) icon_url_short FROM chat_function_buttons LIMIT 20;"')

# 统计 icon 非空
print("\n========= ICON STATS =========")
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -N -e "SELECT COUNT(*) total, SUM(CASE WHEN icon IS NULL OR icon=\\\"\\\" THEN 1 ELSE 0 END) empty_icon FROM chat_function_buttons;"')

# 查 app_settings 的 ai_home_config 简化情况
print("\n========= AI_HOME_CONFIG func_grid =========")
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "SELECT setting_key, JSON_EXTRACT(setting_value, \\\"\\$.func_grid\\\") FROM app_settings WHERE setting_key=\\\"ai_home_config\\\";"')

ssh.close()
