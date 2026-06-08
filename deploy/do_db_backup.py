import paramiko, os, sys
from datetime import datetime

SSH_HOST = "chat.benne-ai.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Benne-ai@#"

DB_HOST = "gz-cdb-nniq1lmp.sql.tencentcdb.com"
DB_PORT = 27082
DB_USER = "root"
DB_PASS = "xiaokang989aab"  # 从 backend 容器获取到的实际密码

LOCAL_DIR = r"C:\buf\db_bak"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DUMP_FILE = f"bini_health_backup_{TIMESTAMP}.sql"
REMOTE_DUMP_PATH = f"/tmp/{DUMP_FILE}"
LOCAL_DUMP_PATH = os.path.join(LOCAL_DIR, DUMP_FILE)

os.makedirs(LOCAL_DIR, exist_ok=True)

print(f"[1/6] 连接 SSH: {SSH_HOST}")
sys.stdout.flush()
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30, banner_timeout=30)
print("  SSH 连接成功")

print(f"[2/6] 检查 mysqldump")
sys.stdout.flush()
stdin, stdout, stderr = ssh.exec_command("which mysqldump 2>&1")
mdp = stdout.read().decode().strip()
print(f"  mysqldump: {mdp if mdp else 'NOT FOUND'}")

if not mdp:
    print("  安装 mysql-client ...")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command("sudo apt-get update -qq && sudo apt-get install -y -qq mysql-client 2>&1", timeout=120)
    inst_out = stdout.read().decode()
    inst_err = stderr.read().decode()
    if inst_out: print(f"  apt: {inst_out[-300:]}")
    if inst_err: print(f"  apt err: {inst_err[-300:]}")
    stdin, stdout, stderr = ssh.exec_command("which mysqldump 2>&1")
    mdp = stdout.read().decode().strip()
    if not mdp:
        print("  安装失败，尝试从 backend 容器导出...")
        mdp = "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend mysqldump"
else:
    mdp = "mysqldump"

print(f"  使用: {mdp}")

print(f"[3/6] 获取数据库列表")
sys.stdout.flush()
db_list_cmd = f"mysql -h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p'{DB_PASS}' -e 'SHOW DATABASES' -N 2>/dev/null"
stdin, stdout, stderr = ssh.exec_command(db_list_cmd, timeout=15)
db_list_out = stdout.read().decode().strip()
if not db_list_out:
    print("  获取失败或没有权限，使用已知数据库: bini_health")
    target_dbs = ["bini_health"]
else:
    all_dbs = [d.strip() for d in db_list_out.split('\n') if d.strip()]
    skip = ['information_schema', 'performance_schema', 'mysql', 'sys']
    target_dbs = [d for d in all_dbs if d not in skip]
print(f"  业务数据库: {target_dbs}")

print(f"[4/6] 执行 mysqldump 导出")
sys.stdout.flush()

# --set-gtid-purged=OFF 避免 GTID 警告，--column-statistics=0 兼容 MySQL 5.7
dump_cmd = (
    f"{mdp} "
    f"-h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p'{DB_PASS}' "
    f"--single-transaction --set-gtid-purged=OFF --column-statistics=0 "
    f"--routines --triggers --events "
    f"--databases " + " ".join(target_dbs) + " "
    f"> {REMOTE_DUMP_PATH}"
)
print(f"  mysqldump -h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p*** --databases {' '.join(target_dbs)} > {REMOTE_DUMP_PATH}")
sys.stdout.flush()

stdin, stdout, stderr = ssh.exec_command(dump_cmd, timeout=600)
exit_code = stdout.channel.recv_exit_status()
dump_err = stderr.read().decode()

if exit_code != 0:
    print(f"  mysqldump 失败 (exit={exit_code}): {dump_err}")
    dump_cmd2 = (
        f"{mdp} "
        f"-h {DB_HOST} -P {DB_PORT} -u {DB_USER} -p'{DB_PASS}' "
        f"--single-transaction --set-gtid-purged=OFF "
        f"--routines "
        f"--databases " + " ".join(target_dbs) + " "
        f"> {REMOTE_DUMP_PATH}"
    )
    print("  重试简化版...")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(dump_cmd2, timeout=600)
    exit_code = stdout.channel.recv_exit_status()
    dump_err = stderr.read().decode()
    if exit_code != 0:
        print(f"  仍然失败 (exit={exit_code}): {dump_err}")
        ssh.close()
        sys.exit(1)
print("  mysqldump 执行完成")

print(f"[5/6] 检查远程文件大小")
sys.stdout.flush()
stdin, stdout, stderr = ssh.exec_command(f"ls -lh {REMOTE_DUMP_PATH} && wc -l {REMOTE_DUMP_PATH}")
print(f"  {stdout.read().decode().strip()}")

print(f"[6/6] 通过 SFTP 下载到本地")
print(f"  远程: {REMOTE_DUMP_PATH}")
print(f"  本地: {LOCAL_DUMP_PATH}")
sys.stdout.flush()

sftp = ssh.open_sftp()
remote_size = sftp.stat(REMOTE_DUMP_PATH).st_size
print(f"  远程文件大小: {remote_size:,} 字节 ({remote_size/1024/1024:.2f} MB)")

# 分块下载大文件
chunk_size = 8 * 1024 * 1024  # 8MB
with sftp.file(REMOTE_DUMP_PATH, 'rb') as rf:
    with open(LOCAL_DUMP_PATH, 'wb') as lf:
        downloaded = 0
        while True:
            chunk = rf.read(chunk_size)
            if not chunk:
                break
            lf.write(chunk)
            downloaded += len(chunk)
            if downloaded % (50 * 1024 * 1024) == 0 or downloaded == remote_size:
                print(f"  下载进度: {downloaded/1024/1024:.1f} / {remote_size/1024/1024:.1f} MB")
                sys.stdout.flush()
sftp.close()

# 清理远程文件
ssh.exec_command(f"rm -f {REMOTE_DUMP_PATH}")
ssh.close()

# 验证
local_size = os.path.getsize(LOCAL_DUMP_PATH)
print(f"\n===== 备份完成 =====")
print(f"本地文件: {LOCAL_DUMP_PATH}")
print(f"文件大小: {local_size:,} 字节 ({local_size/1024/1024:.2f} MB)")
if local_size == remote_size:
    print("校验: 大小一致 ✓")
else:
    print(f"校验: 大小不一致! 远程={remote_size}, 本地={local_size}")

# 检查 SQL 文件头部
with open(LOCAL_DUMP_PATH, 'r', encoding='utf-8', errors='replace') as f:
    head = f.read(500)
print(f"\nSQL 文件头部预览:")
print(head[:400])
print("\n所有操作完成!")
