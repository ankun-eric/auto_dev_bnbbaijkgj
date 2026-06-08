#!/usr/bin/env python3
"""将生产环境数据库数据导入到测试环境（不改变测试环境表结构）。

策略：
1. 上传备份 SQL 到测试服务器
2. 在测试 MySQL 中创建临时数据库 bini_health_tmp
3. 修改备份 SQL 中将数据库名替换为 bini_health_tmp，然后导入
4. 对每个表，获取两个数据库的公共列，构建 INSERT INTO ... SELECT ...
5. 迁移数据完成后删除临时数据库
"""

import paramiko, sys, re, os
from datetime import datetime

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
DB_USER = "root"
DB_PASS = "bini_health_2026"
DB_NAME = "bini_health"
TMP_DB = "bini_health_tmp"

LOCAL_BACKUP = r"C:\buf\db_bak\bini_health_backup_20260607_144728.sql"
REMOTE_BACKUP = "/tmp/prod_backup.sql"
REMOTE_BACKUP_MOD = "/tmp/prod_backup_modified.sql"

def run(ssh, cmd, timeout=60, desc=""):
    if desc:
        print(f"  [{desc}]")
    print(f"  $ {cmd[:200]}")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"    out: {out.strip()[:1500]}")
    if err.strip():
        # Filter mysql warnings
        err_lines = [l for l in err.strip().split('\n') if 'Warning' not in l]
        if err_lines:
            print(f"    err: {'; '.join(err_lines)[:500]}")
    sys.stdout.flush()
    return out, err, exit_code

def mysql_exec(ssh, sql, timeout=30):
    """在测试 MySQL 容器中执行 SQL（通过管道避免 shell 转义问题）"""
    # 用 echo + pipe 方式避免反引号等特殊字符被 shell 解析
    # 用 base64 编码 SQL 来彻底避免转义问题
    import base64
    encoded = base64.b64encode(sql.encode('utf-8')).decode('ascii')
    cmd = f"echo {encoded} | base64 -d | docker exec -i {DB_CONTAINER} mysql -u{DB_USER} -p'{DB_PASS}' 2>&1"
    return run(ssh, cmd, timeout=timeout)

print(f"[STEP 1/7] 连接测试服务器 {SSH_HOST}")
sys.stdout.flush()
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30, banner_timeout=30)
print("  连接成功")

print(f"\n[STEP 2/7] 上传备份 SQL 到测试服务器")
sys.stdout.flush()
sftp = ssh.open_sftp()
local_size = os.path.getsize(LOCAL_BACKUP)
print(f"  本地文件: {LOCAL_BACKUP} ({local_size/1024/1024:.2f} MB)")
# 分块上传
chunk_size = 8 * 1024 * 1024
with open(LOCAL_BACKUP, 'rb') as lf:
    with sftp.file(REMOTE_BACKUP, 'wb') as rf:
        uploaded = 0
        while True:
            chunk = lf.read(chunk_size)
            if not chunk:
                break
            rf.write(chunk)
            uploaded += len(chunk)
            if uploaded % (20 * 1024 * 1024) == 0:
                print(f"  上传进度: {uploaded/1024/1024:.1f} MB")
                sys.stdout.flush()
print(f"  上传完成: {uploaded/1024/1024:.2f} MB")
sftp.close()

print(f"\n[STEP 3/7] 删除旧临时数据库（如存在），创建新临时数据库")
sys.stdout.flush()
out, err, ec = mysql_exec(ssh, f"DROP DATABASE IF EXISTS `{TMP_DB}`")
out, err, ec = mysql_exec(ssh, f"CREATE DATABASE `{TMP_DB}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
if ec != 0:
    print(f"  创建临时数据库失败: {err}")
    ssh.close()
    sys.exit(1)
print(f"  临时数据库 {TMP_DB} 创建成功")

print(f"\n[STEP 4/7] 修改备份 SQL，替换数据库名后导入临时库")
sys.stdout.flush()
# 用 sed 替换: 把 SQL 中的 bini_health 数据库引用替换为 bini_health_tmp
# 替换 CREATE DATABASE 和 USE 语句
sed_cmd = (
    f"sed -e 's/`{DB_NAME}`/`{TMP_DB}`/g' "
    f"-e \"s/Database: {DB_NAME}/Database: {TMP_DB}/g\" "
    f"{REMOTE_BACKUP} > {REMOTE_BACKUP_MOD}"
)
run(ssh, sed_cmd, desc="sed 替换数据库名")

# 检查替换结果
run(ssh, f"head -5 {REMOTE_BACKUP_MOD}", desc="检查修改后的 SQL 头部")

print(f"  导入临时数据库 (这可能需要几分钟)...")
sys.stdout.flush()
import_cmd = f"docker exec -i {DB_CONTAINER} mysql -u{DB_USER} -p'{DB_PASS}' < {REMOTE_BACKUP_MOD} 2>&1"
out, err, ec = run(ssh, import_cmd, timeout=300, desc="执行 mysql 导入")
if ec != 0 and err.strip():
    # 可能有些警告，检查是否真正失败
    if 'ERROR' in err:
        print(f"  导入有错误: {err}")
    else:
        print(f"  导入完成 (可能有警告)")

print(f"  验证临时数据库表数量...")
out, err, ec = mysql_exec(ssh, f"SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema='{TMP_DB}'")
print(f"  临时库表数量: {out.strip()}")

print(f"\n[STEP 5/7] 智能迁移数据: 遍历每个表，匹配公共列后迁移")
sys.stdout.flush()

# 获取两个数据库共有表
out, err, ec = mysql_exec(ssh, 
    f"SELECT TABLE_NAME FROM information_schema.tables "
    f"WHERE table_schema='{TMP_DB}' "
    f"AND TABLE_NAME IN (SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema='{DB_NAME}') "
    f"ORDER BY TABLE_NAME"
)
common_tables = [t.strip() for t in out.strip().split('\n')[1:] if t.strip()]  # skip header
print(f"  两个数据库共有 {len(common_tables)} 个表")

# 对于这些表，需要按照依赖顺序处理（有外键的表先清空子表）
# 简化处理：先禁用外键检查，然后从"叶子"表开始

# 先禁用外键检查
mysql_exec(ssh, "SET FOREIGN_KEY_CHECKS = 0")

skip_tables = []  # 不导入数据的表（如 _migration_bucket_log 等迁移相关）
success_count = 0
fail_count = 0
failed_tables = []

# 获取主数据库中各表的行数（导入前）
print(f"\n  导入前测试库各表行数:")
for tbl in common_tables[:5]:
    out, _, _ = mysql_exec(ssh, f"SELECT COUNT(*) FROM `{DB_NAME}`.`{tbl}`")
    lines = out.strip().split('\n')
    cnt = lines[-1].strip() if len(lines) > 1 else '?'
    print(f"    {tbl}: {cnt}")

# 构建迁移 SQL 脚本：对每个表，找出公共列
print(f"\n  开始逐表迁移...")
sys.stdout.flush()

# 在远程创建迁移脚本
remote_migrate_script = "/tmp/migrate_data.py"
migrate_py = '''import subprocess, sys

DB = "bini_health"
TMP = "bini_health_tmp"
USER = "root"
PASS = "bini_health_2026"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"

def run_mysql(sql, db):
    cmd = ["docker", "exec", CONTAINER, "mysql", "-u"+USER, "-p"+PASS, db, "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = r.returncode == 0 or ("Warning" in r.stderr and "ERROR" not in r.stderr)
    return r.stdout, r.stderr, ok

# Get common tables
out, _, _ = run_mysql("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema='"+TMP+"' AND TABLE_NAME IN (SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema='"+DB+"') ORDER BY TABLE_NAME", DB)
lines = [l.strip() for l in out.strip().split('\\n') if l.strip()]
tables = lines[1:] if len(lines) > 1 else []

total_ok = 0
total_fail = 0
total_skip = 0
failed = []

for tbl in tables:
    # Get columns from target (test) DB
    out, _, _ = run_mysql("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='"+DB+"' AND TABLE_NAME='"+tbl+"' ORDER BY ORDINAL_POSITION", DB)
    target_cols = [c.strip() for c in out.strip().split('\\n')[1:] if c.strip()]
    
    # Get columns from source (prod tmp) DB
    out, _, _ = run_mysql("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='"+TMP+"' AND TABLE_NAME='"+tbl+"' ORDER BY ORDINAL_POSITION", TMP)
    source_cols = [c.strip() for c in out.strip().split('\\n')[1:] if c.strip()]
    
    # Common columns in target order
    common = [c for c in target_cols if c in source_cols]
    
    if not common:
        print("  SKIP %s: no common columns" % tbl)
        total_skip += 1
        continue
    
    cols_quoted = ', '.join(['`%s`' % c for c in common])
    
    # Count source rows
    out, _, _ = run_mysql("SELECT COUNT(*) FROM `"+tbl+"`", TMP)
    try:
        src_count = int(out.strip().split('\\n')[-1].strip() or 0)
    except:
        src_count = 0
    
    # Count target rows before
    out, _, _ = run_mysql("SELECT COUNT(*) FROM `"+tbl+"`", DB)
    try:
        tgt_before = int(out.strip().split('\\n')[-1].strip() or 0)
    except:
        tgt_before = 0
    
    if src_count == 0:
        print("  SKIP %s: source empty, target had %d" % (tbl, tgt_before))
        total_skip += 1
        continue
    
    # Disable FK checks + truncate + insert + re-enable (all in one multi-statement)
    sql = "SET FOREIGN_KEY_CHECKS = 0; DELETE FROM `"+tbl+"`; INSERT INTO `"+tbl+"` ("+cols_quoted+") SELECT "+cols_quoted+" FROM `"+TMP+"`.`"+tbl+"`; SET FOREIGN_KEY_CHECKS = 1;"
    out, err, ok = run_mysql(sql, DB)
    
    if not ok:
        print("  FAIL %s: %s" % (tbl, err[:200]))
        total_fail += 1
        failed.append(tbl)
    else:
        out2, _, _ = run_mysql("SELECT COUNT(*) FROM `"+tbl+"`", DB)
        try:
            tgt_after = int(out2.strip().split('\\n')[-1].strip() or 0)
        except:
            tgt_after = -1
        print("  OK   %s: common=%d cols, imported %d rows (was %d, src %d)" % (tbl, len(common), tgt_after, tgt_before, src_count))
        total_ok += 1

print("\\n===== MIGRATION SUMMARY =====")
print("OK: %d tables" % total_ok)
print("SKIP: %d tables" % total_skip)
print("FAIL: %d tables" % total_fail)
if failed:
    print("FAILED TABLES: %s" % failed)
'''

# Write script to remote
sftp = ssh.open_sftp()
with sftp.file(remote_migrate_script, 'w') as f:
    f.write(migrate_py)
sftp.close()

print("  执行远程迁移脚本...")
sys.stdout.flush()
out, err, ec = run(ssh, f"python3 {remote_migrate_script}", timeout=600, desc="migrate_data.py")

print(f"\n[STEP 6/7] 验证迁移结果")
sys.stdout.flush()
# 检查几个关键表的行数
key_tables = ["users", "chat_messages", "products", "orders" if "orders" in common_tables else "unified_orders"]
for tbl in key_tables:
    if tbl in common_tables:
        out, _, _ = mysql_exec(ssh, f"SELECT COUNT(*) FROM `{DB_NAME}`.`{tbl}`")
        lines = out.strip().split('\n')
        cnt = lines[-1].strip() if len(lines) > 1 else '?'
        print(f"  {DB_NAME}.{tbl}: {cnt} 行")

# 对比两个库的行数
print(f"\n  关键表行数对比 (临时库 vs 测试库):")
sample_tables = common_tables[:10]
for tbl in sample_tables:
    out1, _, _ = mysql_exec(ssh, f"SELECT COUNT(*) FROM `{TMP_DB}`.`{tbl}`")
    cnt1 = out1.strip().split('\n')[-1].strip() if out1.strip() else '?'
    out2, _, _ = mysql_exec(ssh, f"SELECT COUNT(*) FROM `{DB_NAME}`.`{tbl}`")
    cnt2 = out2.strip().split('\n')[-1].strip() if out2.strip() else '?'
    match = "==" if cnt1 == cnt2 else "!="
    print(f"    {tbl}: tmp={cnt1} {match} test={cnt2}")

print(f"\n[STEP 7/7] 清理临时数据库和远程文件")
sys.stdout.flush()
mysql_exec(ssh, f"DROP DATABASE IF EXISTS `{TMP_DB}`")
print(f"  已删除临时数据库 {TMP_DB}")
run(ssh, f"rm -f {REMOTE_BACKUP} {REMOTE_BACKUP_MOD} {remote_migrate_script}", desc="清理远程临时文件")

ssh.close()

print(f"\n===== 数据导入完成 =====")
print(f"生产数据已导入测试环境数据库")
print(f"测试库: {DB_NAME} (docker exec {DB_CONTAINER})")
print(f"表结构: 未改变 (保持测试环境最新结构)")
print(f"数据来源: {LOCAL_BACKUP}")
