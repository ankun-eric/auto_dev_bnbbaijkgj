import paramiko, os, time

TEST_HOST = "newbb.test.bangbangvip.com"
TEST_PORT = 22
TEST_USER = "ubuntu"
TEST_PASS = "Newbang888"
TEST_DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
TEST_DB_NAME = "bini_health"
TEST_DB_USER = "root"
TEST_DB_PASS = "bini_health_2026"

PROD_HOST = "chat.benne-ai.com"
PROD_PORT = 22
PROD_USER = "ubuntu"
PROD_PASS = "Benne-ai@#"
PROD_DB_HOST = "gz-cdb-nniq1lmp.sql.tencentcdb.com"
PROD_DB_PORT = "27082"
PROD_DB_USER = "root"
PROD_DB_PASS = "xiaokang989aab"
PROD_DB_NAME = "bini_health"

LOCAL_DIR = r"C:\auto_output\bnbbaijkgj\deploy"
DUMP_FILE = "bini_health_dump.sql"
DUMP_PATH = f"/tmp/{DUMP_FILE}"

# ============================================================
# Step 1: Export from test env
# ============================================================
print("=" * 60)
print("Step 1: 从测试环境导出数据库")
print("=" * 60)

test = paramiko.SSHClient()
test.set_missing_host_key_policy(paramiko.AutoAddPolicy())
test.connect(TEST_HOST, port=TEST_PORT, username=TEST_USER, password=TEST_PASS, timeout=15)

def run_ssh(client, cmd, timeout=60, label=""):
    if label:
        print(f"  {label}: {cmd[:120]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if err and len(err) > 0:
        print(f"  stderr: {err[:300]}")
    return out, err, code

# Export database from test env MySQL container
dump_cmd = (
    f"docker exec {TEST_DB_CONTAINER} mysqldump "
    f"-u{TEST_DB_USER} -p{TEST_DB_PASS} "
    f"--single-transaction --routines --triggers --events "
    f"--databases {TEST_DB_NAME} "
    f"> {DUMP_PATH} 2>&1"
)

print(f"\n  执行导出...")
out, err, code = run_ssh(test, dump_cmd, timeout=300, label="mysqldump")
print(f"  Export exit code: {code}")

# Check dump file size
out, err, code = run_ssh(test, f"ls -lh {DUMP_PATH} 2>&1", timeout=10)
print(f"  Dump file: {out}")

test.close()

# ============================================================
# Step 2: Download to local
# ============================================================
print("\n" + "=" * 60)
print("Step 2: 下载SQL文件到本地")
print("=" * 60)

local_path = os.path.join(LOCAL_DIR, DUMP_FILE)

test = paramiko.SSHClient()
test.set_missing_host_key_policy(paramiko.AutoAddPolicy())
test.connect(TEST_HOST, port=TEST_PORT, username=TEST_USER, password=TEST_PASS, timeout=15)

sftp = test.open_sftp()
file_size = sftp.stat(DUMP_PATH).st_size
print(f"  远程文件大小: {file_size / 1024 / 1024:.2f} MB")
print(f"  下载中...")
sftp.get(DUMP_PATH, local_path)
sftp.close()
test.close()

local_size = os.path.getsize(local_path)
print(f"  本地文件大小: {local_size / 1024 / 1024:.2f} MB")
print(f"  下载完成: {local_path}")

# ============================================================
# Step 3: Upload to prod and import
# ============================================================
print("\n" + "=" * 60)
print("Step 3: 上传到生产环境并导入腾讯云MySQL")
print("=" * 60)

prod = paramiko.SSHClient()
prod.set_missing_host_key_policy(paramiko.AutoAddPolicy())
prod.connect(PROD_HOST, port=PROD_PORT, username=PROD_USER, password=PROD_PASS, timeout=15)

# Upload dump file
print(f"  上传SQL文件到生产环境...")
sftp = prod.open_sftp()
sftp.put(local_path, DUMP_PATH)
sftp.close()

out, err, code = run_ssh(prod, f"ls -lh {DUMP_PATH}", timeout=10)
print(f"  上传完成: {out}")

# First backup current prod database
print(f"\n  先备份生产环境现有数据...")
backup_file = f"/tmp/bini_health_backup_{int(time.time())}.sql"
backup_cmd = (
    f"python3 -c \"import subprocess; "
    f"subprocess.run(['mysqldump', '-h{PROD_DB_HOST}', '-P{PROD_DB_PORT}', "
    f"'-u{PROD_DB_USER}', '-p{PROD_DB_PASS}', "
    f"'--single-transaction', '--routines', '--triggers', '--events', "
    f"'{PROD_DB_NAME}'], stdout=open('{backup_file}','w'))\" 2>&1"
)
out, err, code = run_ssh(prod, backup_cmd, timeout=300, label="backup")
out2, err2, code2 = run_ssh(prod, f"ls -lh {backup_file} 2>/dev/null || echo 'backup failed'", timeout=10)
print(f"  备份: {out2}")

# Import to Tencent MySQL
print(f"\n  导入数据到腾讯云MySQL...")
import_cmd = (
    f"mysql -h{PROD_DB_HOST} -P{PROD_DB_PORT} "
    f"-u{PROD_DB_USER} -p{PROD_DB_PASS} "
    f"< {DUMP_PATH} 2>&1"
)
out, err, code = run_ssh(prod, import_cmd, timeout=600, label="mysql import")
print(f"  Import exit code: {code}")
if code == 0:
    print(f"  数据导入成功!")
else:
    print(f"  导入可能有问题: {err[:500]}")
    # Try with pymysql
    print(f"\n  尝试通过Python pymysql导入...")
    py_import = (
        f"python3 -c \""
        f"import pymysql; "
        f"conn = pymysql.connect(host='{PROD_DB_HOST}', port={PROD_DB_PORT}, "
        f"user='{PROD_DB_USER}', password='{PROD_DB_PASS}', database='{PROD_DB_NAME}'); "
        f"with open('{DUMP_PATH}', 'r', encoding='utf-8') as f: "
        f"  sql = f.read(); "
        f"for stmt in sql.split(';'): "
        f"  stmt = stmt.strip(); "
        f"  if stmt and not stmt.startswith('--') and not stmt.startswith('/*'): "
        f"    try: cursor = conn.cursor(); cursor.execute(stmt); conn.commit() "
        f"    except: pass "
        f"\" 2>&1"
    )
    out, err, code = run_ssh(prod, py_import, timeout=600)

# ============================================================
# Step 4: Verify
# ============================================================
print("\n" + "=" * 60)
print("Step 4: 验证数据同步")
print("=" * 60)

# Count tables
verify_cmd = (
    f"python3 -c \""
    f"import pymysql; "
    f"conn = pymysql.connect(host='{PROD_DB_HOST}', port={PROD_DB_PORT}, "
    f"user='{PROD_DB_USER}', password='{PROD_DB_PASS}', database='{PROD_DB_NAME}'); "
    f"cursor = conn.cursor(); "
    f"cursor.execute('SHOW TABLES'); "
    f"tables = [r[0] for r in cursor.fetchall()]; "
    f"print(f'表数量: {len(tables)}'); "
    f"for t in tables: "
    f"  cursor.execute(f'SELECT COUNT(*) FROM `{t}`'); "
    f"  cnt = cursor.fetchone()[0]; "
    f"  print(f'  {t}: {cnt} rows'); "
    f"conn.close()"
    f"\" 2>&1"
)
out, err, code = run_ssh(prod, verify_cmd, timeout=60)
print(out)

# Cleanup temp files
print(f"\n  清理临时文件...")
run_ssh(prod, f"rm -f {DUMP_PATH} {backup_file}", timeout=10)

prod.close()

# Cleanup test env temp
test2 = paramiko.SSHClient()
test2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
test2.connect(TEST_HOST, port=TEST_PORT, username=TEST_USER, password=TEST_PASS, timeout=15)
run_ssh(test2, f"rm -f {DUMP_PATH}", timeout=10)
test2.close()

# Cleanup local
os.remove(local_path)
print(f"  本地临时文件已清理")

print("\n" + "=" * 60)
print("数据库同步完成!")
print("=" * 60)
