#!/usr/bin/env python3
"""通过 SSH 在生产服务器上执行 mysqldump，将全部数据库导出并下载到本地。"""

import paramiko
import os
import sys
from datetime import datetime

SSH_HOST = "chat.benne-ai.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Benne-ai@#"

DB_HOST = "gz-cdb-nniq1lmp.sql.tencentcdb.com"
DB_PORT = 27082
DB_USER = "root"
DB_PASS = "xiaokangaab"

LOCAL_DIR = r"C:\buf\db_bak"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DUMP_FILE = f"all_databases_{TIMESTAMP}.sql"
REMOTE_DUMP_PATH = f"/tmp/{DUMP_FILE}"
LOCAL_DUMP_PATH = os.path.join(LOCAL_DIR, DUMP_FILE)

os.makedirs(LOCAL_DIR, exist_ok=True)

print(f"[1/5] 连接 SSH: {SSH_HOST}:{SSH_PORT} ...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30, banner_timeout=30)
    print("  SSH 连接成功")
except Exception as e:
    print(f"  SSH 连接失败: {e}")
    sys.exit(1)

print(f"[2/5] 检查 mysqldump 是否可用...")
stdin, stdout, stderr = ssh.exec_command("which mysqldump || echo NOT_FOUND")
mysqldump_path = stdout.read().decode().strip()
print(f"  mysqldump: {mysqldump_path}")

if "NOT_FOUND" in mysqldump_path:
    print("  尝试安装 mysql-client ...")
    ssh.exec_command("sudo apt-get update -qq && sudo apt-get install -y -qq mysql-client 2>&1")
    # 重新检查
    stdin, stdout, stderr = ssh.exec_command("which mysqldump")
    mysqldump_path = stdout.read().decode().strip()
    if not mysqldump_path:
        print("  安装失败，尝试用 python + pymysql 导出...")
        # fallback: 在远程服务器上检查 python
        stdin, stdout, stderr = ssh.exec_command("python3 --version 2>&1 || python --version 2>&1")
        pyver = stdout.read().decode().strip()
        print(f"  远程 Python: {pyver}")

if mysqldump_path:
    print(f"[3/5] 在服务器上执行 mysqldump 导出全部数据库...")
    dump_cmd = (
        f"{mysqldump_path} "
        f"-h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p'{DB_PASS}' "
        f"--single-transaction --routines --triggers --events "
        f"--all-databases "
        f"> {REMOTE_DUMP_PATH}"
    )
    print(f"  执行命令: mysqldump -h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p*** --all-databases > {REMOTE_DUMP_PATH}")
    stdin, stdout, stderr = ssh.exec_command(dump_cmd, timeout=600)
    exit_status = stdout.channel.recv_exit_status()
    stderr_output = stderr.read().decode()
    if exit_status != 0:
        print(f"  mysqldump 失败 (exit={exit_status}): {stderr_output}")
        # 尝试不带 --events 和 --triggers（低版本 MySQL 可能不支持）
        dump_cmd2 = (
            f"{mysqldump_path} "
            f"-h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p'{DB_PASS}' "
            f"--single-transaction --routines "
            f"--all-databases "
            f"> {REMOTE_DUMP_PATH}"
        )
        print("  重试简化版...")
        stdin, stdout, stderr = ssh.exec_command(dump_cmd2, timeout=600)
        exit_status = stdout.channel.recv_exit_status()
        stderr_output = stderr.read().decode()
        if exit_status != 0:
            print(f"  仍然失败 (exit={exit_status}): {stderr_output}")
            ssh.close()
            sys.exit(1)
    print("  mysqldump 执行完成")

    print(f"[4/5] 检查导出文件大小...")
    stdin, stdout, stderr = ssh.exec_command(f"ls -lh {REMOTE_DUMP_PATH}")
    print(f"  {stdout.read().decode().strip()}")

    print(f"[5/5] 通过 SFTP 下载到本地: {LOCAL_DUMP_PATH}")
    sftp = ssh.open_sftp()
    sftp.get(REMOTE_DUMP_PATH, LOCAL_DUMP_PATH)
    sftp.close()
    print("  下载完成")

    # 清理远程临时文件
    ssh.exec_command(f"rm -f {REMOTE_DUMP_PATH}")

    # 验证本地文件
    local_size = os.path.getsize(LOCAL_DUMP_PATH)
    print(f"\n===== 备份完成 =====")
    print(f"本地文件: {LOCAL_DUMP_PATH}")
    print(f"文件大小: {local_size:,} 字节 ({local_size/1024/1024:.2f} MB)")
else:
    print("[3/5] mysqldump 不可用，使用 Python pymysql 在服务器上导出...")
    remote_script = f'''
import pymysql
import os
from datetime import datetime

DB_HOST = "{DB_HOST}"
DB_PORT = {DB_PORT}
DB_USER = "{DB_USER}"
DB_PASS = "{DB_PASS}"
OUT_PATH = "{REMOTE_DUMP_PATH}"

print("连接数据库...")
conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, charset='utf8mb4')
cursor = conn.cursor()

print("获取数据库列表...")
cursor.execute("SHOW DATABASES")
dbs = [r[0] for r in cursor.fetchall()]
skip = ['information_schema', 'performance_schema', 'mysql', 'sys']
targets = [d for d in dbs if d not in skip]
print(f"待导出数据库: {{targets}}")

total_size = 0
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(f"-- MySQL Dump (by pymysql)\\n")
    f.write(f"-- Date: {{datetime.now()}}\\n\\n")
    f.write("SET NAMES utf8mb4;\\n")
    f.write("SET FOREIGN_KEY_CHECKS = 0;\\n\\n")

    for db in targets:
        print(f"导出数据库: {{db}} ...")
        f.write(f"\\n-- Database: {{db}}\\n")
        f.write(f"CREATE DATABASE IF NOT EXISTS `{{db}}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\\n")
        f.write(f"USE `{{db}}`;\\n\\n")

        cursor.execute(f"USE `{{db}}`")
        cursor.execute("SHOW TABLES")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"  共 {{len(tables)}} 张表")

        for table in tables:
            print(f"    导出: {{table}}")
            # CREATE TABLE
            cursor.execute(f"SHOW CREATE TABLE `{{table}}`")
            create_sql = cursor.fetchone()[1]
            f.write(f"DROP TABLE IF EXISTS `{{table}}`;\\n")
            f.write(f"{{create_sql}};\\n\\n")

            # SELECT all rows
            cursor.execute(f"SELECT * FROM `{{table}}`")
            rows = cursor.fetchall()
            if rows:
                cols = [d[0] for d in cursor.description]
                col_list = ', '.join([f'`{{c}}`' for c in cols])
                for row in rows:
                    vals = []
                    for v in row:
                        if v is None:
                            vals.append('NULL')
                        elif isinstance(v, (int, float)):
                            vals.append(str(v))
                        else:
                            vals.append("'" + str(v).replace("\\\\", "\\\\\\\\").replace("'", "\\\\'") + "'")
                    f.write(f"INSERT INTO `{{table}}` ({{col_list}}) VALUES ({{', '.join(vals)}});\\n")
                f.write("\\n")

    f.write("SET FOREIGN_KEY_CHECKS = 1;\\n")

conn.close()

total_size = os.path.getsize(OUT_PATH)
print(f"\\n导出完成! 文件: {{OUT_PATH}}, 大小: {{total_size}} bytes")
'''
    # 写入远程脚本
    sftp = ssh.open_sftp()
    remote_script_path = "/tmp/db_backup_remote.py"
    with sftp.file(remote_script_path, 'w') as f:
        f.write(remote_script)
    sftp.close()

    # 检查远程 pymysql
    stdin, stdout, stderr = ssh.exec_command("python3 -c 'import pymysql' 2>&1")
    py_check = stdout.read().decode() + stderr.read().decode()
    if "ModuleNotFoundError" in py_check or "No module" in py_check:
        print("  远程安装 pymysql...")
        stdin2, stdout2, stderr2 = ssh.exec_command("sudo pip3 install pymysql 2>&1", timeout=120)
        o2 = stdout2.read().decode()
        e2 = stderr2.read().decode()
        if o2: print(f"  pip: {o2[-300:]}")
        if e2: print(f"  pip err: {e2[-300:]}")

    print("  执行远程导出脚本...")
    stdin, stdout, stderr = ssh.exec_command(f"python3 {remote_script_path}", timeout=1800)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(f"  stdout: {out[-500:] if len(out)>500 else out}")
    if err:
        print(f"  stderr: {err[-1000:] if len(err)>1000 else err}")

    print(f"[4/5] 检查导出文件大小...")
    stdin, stdout, stderr = ssh.exec_command(f"ls -lh {REMOTE_DUMP_PATH}")
    print(f"  {stdout.read().decode().strip()}")

    print(f"[5/5] 通过 SFTP 下载到本地: {LOCAL_DUMP_PATH}")
    sftp = ssh.open_sftp()
    sftp.get(REMOTE_DUMP_PATH, LOCAL_DUMP_PATH)
    sftp.close()
    print("  下载完成")

    # 清理
    ssh.exec_command(f"rm -f {REMOTE_DUMP_PATH} {remote_script_path}")

    local_size = os.path.getsize(LOCAL_DUMP_PATH)
    print(f"\n===== 备份完成 =====")
    print(f"本地文件: {LOCAL_DUMP_PATH}")
    print(f"文件大小: {local_size:,} 字节 ({local_size/1024/1024:.2f} MB)")

ssh.close()
print("\n所有操作完成!")
