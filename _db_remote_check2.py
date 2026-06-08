#!/usr/bin/env python3
"""通过 SSH 远程查询数据库 - 第2版，找到正确的 MySQL 容器"""
import paramiko

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

    # 找到 6b099ed3 项目的 MySQL 容器
    out, err = run("docker ps --format '{{.Names}}' | grep 6b099ed3")
    print(f"=== 6b099ed3 容器列表 ===\n{out}")

    # 查看 docker-compose 文件
    out, err = run(f"cat {PROJECT_DIR}/docker-compose.yml 2>/dev/null | head -60")
    print(f"\n=== docker-compose.yml ===\n{out}")

    # 查看所有 MySQL 容器的环境变量
    out, err = run("for c in $(docker ps --format '{{.Names}}' | grep -i mysql); do echo \"=== $c ===\"; docker inspect $c --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -i -E 'MYSQL_ROOT|MYSQL_DATABASE|MYSQL_PASSWORD'; echo; done")
    print(f"\n=== MySQL 容器环境变量 ===\n{out}")

    # 找到属于 6b099ed3 项目的 MySQL 容器，直接用 docker exec 连
    out, err = run("DB_CONTAINER=$(docker ps --format '{{.Names}}' | grep '6b099ed3.*mysql\\|6b099ed3.*db'); echo \"容器: $DB_CONTAINER\"; docker exec $DB_CONTAINER mysql -uroot -p'$MYSQL_ROOT_PASSWORD' -e \"SELECT 1\" 2>&1 || docker exec $DB_CONTAINER mysql -uroot -proot -e \"SELECT 1\" 2>&1 || echo \"需要查密码\"")
    print(f"\n=== 尝试连接 ===\n{out}")

    # 查看 6b099ed3-db 容器的环境变量
    out, err = run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-db --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null")
    print(f"\n=== 6b099ed3-db 环境变量 ===\n{out}")

finally:
    client.close()
    print("\n[OK] SSH 已断开")
