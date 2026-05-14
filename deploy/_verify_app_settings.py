#!/usr/bin/env python3
import paramiko, sys, json

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

# 列出所有表，找到 ai_home_config 的存储位置
print("\n========= TABLES =========")
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "SHOW TABLES LIKE \\\"%setting%\\\";"')
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "SHOW TABLES LIKE \\\"%home%\\\";"')
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "SHOW TABLES LIKE \\\"%config%\\\";"')
sh(f'docker exec -e MYSQL_PWD={MYSQL_PWD} {DB} mysql -uroot bini_health -B -e "SHOW TABLES LIKE \\\"%ai_%\\\";"')

ssh.close()
