#!/usr/bin/env python3
"""通过 SSH 远程查询数据库"""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

try:
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15,
                   look_for_keys=False, allow_agent=False, banner_timeout=15)
    print("[OK] SSH 连接成功")

    # 查看 docker-compose 或 .env 找数据库连接方式
    out, err = run(f"cat {PROJECT_DIR}/.env 2>/dev/null | head -20")
    print(f"\n=== 项目 .env ===\n{out}")
    if err:
        print(f"stderr: {err}")

    out, err = run(f"cat {PROJECT_DIR}/backend/.env 2>/dev/null | head -20")
    print(f"\n=== backend/.env ===\n{out}")
    if err:
        print(f"stderr: {err}")

    # 查看 docker 容器
    out, err = run("docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' 2>/dev/null | head -20")
    print(f"\n=== Docker 容器 ===\n{out}")

    # 查找 MySQL 容器
    out, err = run("docker ps --format '{{.Names}}' 2>/dev/null | grep -i mysql")
    print(f"\n=== MySQL 容器 ===\n{out}")

    # 尝试直接连 MySQL
    out, err = run("docker exec $(docker ps --format '{{.Names}}' | grep -i mysql | head -1) mysql -uroot -pbini_health_2026 -e \"SELECT id, user_id, family_member_id, name, gender, birth_date FROM bini_health.health_profiles WHERE user_id = 18 AND family_member_id IS NULL\" 2>&1")
    print(f"\n=== 查询结果 ===\n{out}")
    if err:
        print(f"stderr: {err}")

    # 也查一下全部 user_id=18 的记录
    out, err = run("docker exec $(docker ps --format '{{.Names}}' | grep -i mysql | head -1) mysql -uroot -pbini_health_2026 -e \"SELECT id, user_id, family_member_id, name FROM bini_health.health_profiles WHERE user_id = 18\" 2>&1")
    print(f"\n=== user_id=18 全部记录 ===\n{out}")

finally:
    client.close()
    print("\n[OK] SSH 已断开")
