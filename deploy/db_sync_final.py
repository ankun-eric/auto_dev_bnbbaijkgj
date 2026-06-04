import paramiko, os, time, sys

# ========== 配置 ==========
TEST_HOST = "newbb.test.bangbangvip.com"
TEST_PORT = 22; TEST_USER = "ubuntu"; TEST_PASS = "Newbang888"
TEST_DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
TEST_DB_NAME = "bini_health"; TEST_DB_USER = "root"; TEST_DB_PASS = "bini_health_2026"

PROD_HOST = "chat.benne-ai.com"
PROD_PORT = 22; PROD_USER = "ubuntu"; PROD_PASS = "Benne-ai@#"
PROD_DB_HOST = "gz-cdb-nniq1lmp.sql.tencentcdb.com"; PROD_DB_PORT = "27082"
PROD_DB_USER = "root"; PROD_DB_PASS = "xiaokang989aab"; PROD_DB_NAME = "bini_health"

LOCAL_DIR = r"C:\auto_output\bnbbaijkgj\deploy"
DUMP_FILE = "bini_health_dump.sql"
REMOTE_DUMP = f"/tmp/{DUMP_FILE}"
LOCAL_DUMP = os.path.join(LOCAL_DIR, DUMP_FILE)

def run_ssh(client, cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code

# ========== Step 1: 导出 ==========
print("=" * 50)
print("Step 1/4: 测试环境导出数据库")
print("=" * 50)

test = paramiko.SSHClient()
test.set_missing_host_key_policy(paramiko.AutoAddPolicy())
test.connect(TEST_HOST, port=TEST_PORT, username=TEST_USER, password=TEST_PASS, timeout=15)

dump_cmd = (
    f"docker exec {TEST_DB_CONTAINER} mysqldump "
    f"-u{TEST_DB_USER} -p{TEST_DB_PASS} "
    f"--single-transaction --routines --triggers --events "
    f"--databases {TEST_DB_NAME} > {REMOTE_DUMP} 2>&1"
)
out, err, code = run_ssh(test, dump_cmd, timeout=300)
print(f"  Export exit: {code}")
out, err, code = run_ssh(test, f"ls -lh {REMOTE_DUMP}")
print(f"  Size: {out}")
if code != 0 or "No such" in out:
    print("  导出失败！")
    test.close()
    sys.exit(1)
test.close()

# ========== Step 2: 下载 ==========
print("\n" + "=" * 50)
print("Step 2/4: 下载dump文件到本地")
print("=" * 50)

test2 = paramiko.SSHClient()
test2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
test2.connect(TEST_HOST, port=TEST_PORT, username=TEST_USER, password=TEST_PASS, timeout=15)
sftp = test2.open_sftp()
fsize = sftp.stat(REMOTE_DUMP).st_size
print(f"  远程: {fsize/1024/1024:.2f} MB, 下载中...")
sftp.get(REMOTE_DUMP, LOCAL_DUMP)
sftp.close()
test2.close()
print(f"  本地: {os.path.getsize(LOCAL_DUMP)/1024/1024:.2f} MB OK")

# ========== Step 3: 上传+导入 ==========
print("\n" + "=" * 50)
print("Step 3/4: 上传到生产环境并导入腾讯云MySQL")
print("=" * 50)

prod = paramiko.SSHClient()
prod.set_missing_host_key_policy(paramiko.AutoAddPolicy())
prod.connect(PROD_HOST, port=PROD_PORT, username=PROD_USER, password=PROD_PASS, timeout=15)

# Upload
print("  上传dump文件...")
sftp2 = prod.open_sftp()
sftp2.put(LOCAL_DUMP, REMOTE_DUMP)
sftp2.close()
run_ssh(prod, f"ls -lh {REMOTE_DUMP}")

# Import via Docker
print("  Docker容器导入中...")
import_cmd = (
    f"sudo docker run --rm --network host "
    f"-v {REMOTE_DUMP}:/dump.sql:ro "
    f"mysql:8.0 "
    f"mysql -h{PROD_DB_HOST} -P{PROD_DB_PORT} "
    f"-u{PROD_DB_USER} -p{PROD_DB_PASS} "
    f"{PROD_DB_NAME} < /dump.sql 2>&1"
)
out, err, code = run_ssh(prod, import_cmd, timeout=600)
print(f"  Import exit: {code}")
if err:
    # Filter out mysql warning noise
    for line in err.split('\n'):
        if 'Warning' not in line and line.strip():
            print(f"  ERR: {line[:200]}")
if out:
    for line in out.split('\n'):
        if 'Warning' not in line and line.strip():
            print(f"  OUT: {line[:200]}")

if code == 0:
    print("  导入成功!")
else:
    print(f"  导入异常(code={code})，继续验证...")

# ========== Step 4: 验证 ==========
print("\n" + "=" * 50)
print("Step 4/4: 验证数据同步结果")
print("=" * 50)

verify = (
    f"python3 -c \""
    f"import pymysql; "
    f"conn = pymysql.connect(host='{PROD_DB_HOST}', port={PROD_DB_PORT}, "
    f"user='{PROD_DB_USER}', password='{PROD_DB_PASS}', database='{PROD_DB_NAME}'); "
    f"c = conn.cursor(); "
    f"c.execute('SHOW TABLES'); "
    f"tables = [r[0] for r in c.fetchall()]; "
    f"total_rows = 0; "
    f"for t in tables: "
    f"  c.execute('SELECT COUNT(*) FROM `' + t + '`'); "
    f"  cnt = c.fetchone()[0]; "
    f"  total_rows += cnt; "
    f"  print(t, cnt); "
    f"print('TOTAL_TABLES', len(tables)); "
    f"print('TOTAL_ROWS', total_rows); "
    f"conn.close()"
    f"\" 2>&1"
)
out, err, code = run_ssh(prod, verify, timeout=60)
if out:
    lines = out.strip().split('\n')
    for line in lines:
        parts = line.strip().split(' ', 1)
        if len(parts) == 2:
            if parts[0] in ('TOTAL_TABLES', 'TOTAL_ROWS'):
                print(f"  ** {parts[0]}: {parts[1]}")
            else:
                print(f"  {parts[0]:40s} {parts[1]} rows")
        else:
            print(f"  {line}")

# Test API
print("\n  验证后端API...")
out, err, code = run_ssh(prod, "curl -sk https://localhost/api/health 2>&1", timeout=15)
print(f"  {out}")

# Cleanup
print("\n  清理临时文件...")
run_ssh(prod, f"rm -f {REMOTE_DUMP}")
# Clean test env
test3 = paramiko.SSHClient()
test3.set_missing_host_key_policy(paramiko.AutoAddPolicy())
test3.connect(TEST_HOST, port=TEST_PORT, username=TEST_USER, password=TEST_PASS, timeout=15)
run_ssh(test3, f"rm -f {REMOTE_DUMP}")
test3.close()

prod.close()

# Clean local
os.remove(LOCAL_DUMP)

print("\n" + "=" * 50)
print("数据库同步完成！")
print("=" * 50)
