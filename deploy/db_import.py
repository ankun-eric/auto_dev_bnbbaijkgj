import paramiko

PROD_HOST = "chat.benne-ai.com"
PROD_USER = "ubuntu"; PROD_PASS = "Benne-ai@#"
PROD_DB_HOST = "gz-cdb-nniq1lmp.sql.tencentcdb.com"; PROD_DB_PORT = "27082"
PROD_DB_USER = "root"; PROD_DB_PASS = "xiaokang989aab"; PROD_DB_NAME = "bini_health"
DUMP_FILE = "/tmp/bini_health_dump.sql"

prod = paramiko.SSHClient()
prod.set_missing_host_key_policy(paramiko.AutoAddPolicy())
prod.connect(PROD_HOST, port=22, username=PROD_USER, password=PROD_PASS, timeout=15)

def run(cmd, timeout=120):
    print(f"  CMD: {cmd[:140]}")
    stdin, stdout, stderr = prod.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out:
        for line in out.split('\n'):
            if 'Warning' not in line and line.strip():
                print(f"  OUT: {line[:200]}")
    if err:
        for line in err.split('\n'):
            if 'Warning' not in line and line.strip():
                print(f"  ERR: {line[:200]}")
    return out, err, code

# Check dump exists
print("=== 确认dump文件 ===")
run(f"ls -lh {DUMP_FILE}")

# Import: use bash -c to handle redirection inside container
print("\n=== Docker容器导入 ===")
import_cmd = (
    f'sudo docker run --rm --network host '
    f'-v {DUMP_FILE}:/dump.sql:ro mysql:8.0 '
    f'bash -c "mysql -h{PROD_DB_HOST} -P{PROD_DB_PORT} '
    f'-u{PROD_DB_USER} -p{PROD_DB_PASS} '
    f'{PROD_DB_NAME} < /dump.sql" 2>&1'
)
out, err, code = run(import_cmd, timeout=600)
print(f"\n  Import exit code: {code}")

# Verify
print("\n=== 验证数据 ===")
verify = (
    "python3 -c \"import pymysql; "
    f"conn = pymysql.connect(host='{PROD_DB_HOST}', port={PROD_DB_PORT}, user='{PROD_DB_USER}', password='{PROD_DB_PASS}', database='{PROD_DB_NAME}'); "
    "c = conn.cursor(); "
    "c.execute('SHOW TABLES'); "
    "tables = [r[0] for r in c.fetchall()]; "
    "for t in tables: "
    "  c.execute('SELECT COUNT(*) FROM ' + t); "
    "  cnt = c.fetchone()[0]; "
    "  print(t, cnt); "
    "conn.close()\""
)
out, err, code = run(verify, timeout=60)
if out:
    for line in out.strip().split('\n'):
        parts = line.strip().split(' ', 1)
        if len(parts) == 2:
            print(f"  {parts[0]:40s} {parts[1]:>8s} rows")
        else:
            print(f"  {line}")

# Test API
print("\n=== API检查 ===")
out, err, code = run("curl -sk https://localhost/api/health 2>&1", timeout=15)
print(f"  {out}")

# Cleanup
run(f"rm -f {DUMP_FILE}")
prod.close()
print("\n=== 完成 ===")
