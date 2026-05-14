#!/usr/bin/env python3
"""Check migration log on server."""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def sh(cmd):
    print(f">>> {cmd[:120]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(f"[stderr] {err.strip()[:300]}")

# 1. 全量 backend 启动日志（最近 500 行）
sh(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | head -200")
print("\n\n========== TAIL 200 ==========\n\n")
sh(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | tail -200")

# 2. 查 icon 数据
sh(f"docker exec {PROJECT_ID}-mysql sh -c 'mysql -uroot -proot -N -B -e \"SELECT id, name, icon, icon_url FROM bini_health.chat_function_buttons LIMIT 20;\" 2>/dev/null || echo NOT_AVAILABLE'")

# 3. 查表结构
sh(f"docker exec {PROJECT_ID}-mysql sh -c 'mysql -uroot -proot -B -e \"DESC bini_health.chat_function_buttons;\" 2>/dev/null || echo NOT_AVAILABLE'")

# 4. 查 ai_home_config（func_grid）
sh(f"docker exec {PROJECT_ID}-mysql sh -c 'mysql -uroot -proot -B -e \"SELECT setting_key, LEFT(setting_value, 500) FROM bini_health.app_settings WHERE setting_key=\\\"ai_home_config\\\";\" 2>/dev/null || echo NOT_AVAILABLE'")

ssh.close()
