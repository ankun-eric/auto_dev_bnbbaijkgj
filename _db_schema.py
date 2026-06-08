#!/usr/bin/env python3
"""远程查询数据库 - 先看表结构"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
DB_PWD = "bini_health_2026"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def mysql_query(sql):
    cmd = f"docker exec {DB_CONTAINER} mysql -uroot -p'{DB_PWD}' -h127.0.0.1 bini_health -e \"{sql}\" 2>&1"
    out, err = run(cmd)
    return out

try:
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15,
                   look_for_keys=False, allow_agent=False, banner_timeout=15)
    print("[OK] SSH 连接成功\n")

    # 查看 health_profiles 表结构
    print("=== health_profiles 表结构 ===")
    result = mysql_query("DESCRIBE health_profiles")
    print(result)

    # 查看 family_invitations 表结构
    print("=== family_invitations 表结构 ===")
    result = mysql_query("DESCRIBE family_invitations")
    print(result)

    # 查看 family_management 表结构
    print("=== family_management 表结构 ===")
    result = mysql_query("DESCRIBE family_management")
    print(result)

finally:
    client.close()
    print("[OK] SSH 已断开")
