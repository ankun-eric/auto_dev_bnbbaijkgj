#!/usr/bin/env python3
"""通过 SSH 远程查询数据库 - 第3版"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"

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

    DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
    PWD_DB = "bini_health_2026"

    # 尝试多种连接方式
    cmds = [
        f'docker exec {DB_CONTAINER} mysql -uroot -p"{PWD_DB}" -h127.0.0.1 -e "SELECT 1" 2>&1',
        f'docker exec {DB_CONTAINER} mysql -uroot -p"{PWD_DB}" --protocol=TCP -h127.0.0.1 -e "SELECT 1" 2>&1',
        f'docker exec {DB_CONTAINER} mysql -uroot -p"{PWD_DB}" --socket=/var/run/mysqld/mysqld.sock -e "SELECT 1" 2>&1',
        f'docker exec {DB_CONTAINER} sh -c "mysql -uroot -p\'{PWD_DB}\' -e \'SELECT 1\'" 2>&1',
    ]
    for i, cmd in enumerate(cmds):
        out, err = run(cmd)
        print(f"\n=== 方式{i+1} ===\n{out}{err}")

    # 查看 MySQL 的认证插件
    out, err = run(f'docker exec {DB_CONTAINER} mysql -uroot -p"{PWD_DB}" -e "SELECT user,host,plugin FROM mysql.user WHERE user=\'root\'" 2>&1')
    print(f"\n=== root用户信息 ===\n{out}{err}")

    # 尝试用 mysql_native_password
    out, err = run(f'docker exec {DB_CONTAINER} mysql -uroot -p"{PWD_DB}" --default-auth=mysql_native_password -e "SELECT 1" 2>&1')
    print(f"\n=== mysql_native_password ===\n{out}{err}")

finally:
    client.close()
    print("\n[OK] SSH 已断开")
