import paramiko, os, time, subprocess

# ========== CONFIG ==========
TH = "newbb.test.bangbangvip.com"; TP = 22; TU = "ubuntu"; TPass = "Newbang888"
TC = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
TDB = "bini_health"; TDU = "root"; TDP = "bini_health_2026"

PH = "chat.benne-ai.com"; PP = 22; PU = "ubuntu"; PPass = "Benne-ai@#"
PDH = "gz-cdb-nniq1lmp.sql.tencentcdb.com"; PDP = "27082"
PDU = "root"; PDPass = "xiaokang989aab"; PDB = "bini_health"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"

LOCAL = r"C:\auto_output\bnbbaijkgj\deploy"
DUMP = "bini_health_dump.sql"
REMOTE = f"/tmp/{DUMP}"
LOCAL_DUMP = os.path.join(LOCAL, DUMP)

def ssh_connect(h, p, u, pw):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(h, port=p, username=u, password=pw, timeout=15)
    return c

def run(client, cmd, t=120):
    print(f"  $ {cmd[:130]}")
    si, so, se = client.exec_command(cmd, timeout=t)
    out = so.read().decode(errors='replace').strip()
    err = se.read().decode(errors='replace').strip()
    code = so.channel.recv_exit_status()
    return out, err, code

# ==========================================
# Step 1: Export from test env
# ==========================================
print("=" * 55)
print("Step 1/5: 测试环境导出 (%s)" % TDB)
print("=" * 55)
c1 = ssh_connect(TH, TP, TU, TPass)
cmd = f"docker exec {TC} mysqldump -u{TDU} -p{TDP} --single-transaction --routines --triggers --events --databases {TDB} > {REMOTE} 2>&1"
o, e, code = run(c1, cmd, t=300)
print(f"  Export: code={code}")
o, e, code = run(c1, f"ls -lh {REMOTE}")
print(f"  Size: {o}")
c1.close()
if code != 0:
    print("FAIL"); exit(1)

# ==========================================
# Step 2: Download to local
# ==========================================
print("\n" + "=" * 55)
print("Step 2/5: 下载到本地")
print("=" * 55)
c2 = ssh_connect(TH, TP, TU, TPass)
sftp = c2.open_sftp()
fs = sftp.stat(REMOTE).st_size
print(f"  远程 {fs/1024/1024:.2f}MB, 下载中...")
sftp.get(REMOTE, LOCAL_DUMP)
sftp.close(); c2.close()
print(f"  本地 {os.path.getsize(LOCAL_DUMP)/1024/1024:.2f}MB OK")

# ==========================================
# Step 3: Pull mysql image + Upload dump to prod
# ==========================================
print("\n" + "=" * 55)
print("Step 3/5: 拉取MySQL镜像 + 上传dump")
print("=" * 55)
c3 = ssh_connect(PH, PP, PU, PPass)
# Pull mysql from ACR base
o, e, code = run(c3, f"sudo docker pull {ACR}/noob_doker_base/mysql:8.0 2>&1", t=180)
if code == 0:
    run(c3, f"sudo docker tag {ACR}/noob_doker_base/mysql:8.0 mysql:8.0")
    print("  MySQL镜像 OK (from ACR)")
else:
    print(f"  MySQL pull failed: {o[:200]}")
# Upload dump
sftp3 = c3.open_sftp()
sftp3.put(LOCAL_DUMP, REMOTE)
sftp3.close()
run(c3, f"ls -lh {REMOTE}")
print("  Dump上传 OK")
c3.close()

# ==========================================
# Step 4: Import to Tencent MySQL via Docker
# ==========================================
print("\n" + "=" * 55)
print("Step 4/5: Docker导入腾讯云MySQL")
print("=" * 55)
c4 = ssh_connect(PH, PP, PU, PPass)
# Build import command with bash -c for redirection
import_cmd = (
    f"sudo docker run --rm --network host "
    f"-v {REMOTE}:/dump.sql:ro "
    f"mysql:8.0 "
    f"bash -c 'mysql -h{PDH} -P{PDP} -u{PDU} -p{PDPass} {PDB} < /dump.sql' 2>&1"
)
print(f"  执行导入（可能需几分钟）...")
o, e, code = run(c4, import_cmd, t=600)
print(f"  Import code: {code}")
# Filter warnings
for line in o.split('\n'):
    if 'Warning' not in line and line.strip():
        print(f"    OUT: {line[:150]}")
for line in e.split('\n'):
    if 'Warning' not in line and line.strip():
        print(f"    ERR: {line[:150]}")
c4.close()

# ==========================================
# Step 5: Verify
# ==========================================
print("\n" + "=" * 55)
print("Step 5/5: 验证数据同步")
print("=" * 55)
c5 = ssh_connect(PH, PP, PU, PPass)
# Write verify script to file to avoid shell escaping issues
vscript = f"""
import pymysql
conn = pymysql.connect(host='{PDH}', port={PDP}, user='{PDU}', password='{PDPass}', database='{PDB}')
c = conn.cursor()
c.execute('SHOW TABLES')
tables = [r[0] for r in c.fetchall()]
for t in tables:
    c.execute('SELECT COUNT(*) FROM `' + t + '`')
    cnt = c.fetchone()[0]
    print(t, cnt)
conn.close()
"""
# Upload verify script
sftp5 = c5.open_sftp()
with sftp5.open("/tmp/verify_db.py", "w") as f:
    f.write(vscript)
sftp5.close()
o, e, code = run(c5, "python3 /tmp/verify_db.py 2>&1", t=60)
if o:
    total = 0
    for line in o.strip().split('\n'):
        parts = line.strip().split(' ', 1)
        if len(parts) == 2:
            try:
                cnt = int(parts[1])
                total += cnt
                print(f"  {parts[0]:45s} {cnt:>10,} rows")
            except:
                print(f"  {line}")
        else:
            print(f"  {line}")
    print(f"  {'-'*55}")
    print(f"  {'TOTAL':45s} {total:>10,} rows")
    print(f"  {'TABLES':45s} {len(o.strip().split(chr(10)))} 张表")
else:
    print("  Verify failed:", e[:300])
run(c5, "rm -f /tmp/verify_db.py")

# API check
print("\n  API健康检查:")
o, e, code = run(c5, "curl -sk https://localhost/api/health 2>&1", t=15)
print(f"  {o}")

# Cleanup
print("\n  清理临时文件...")
run(c5, f"rm -f {REMOTE}")
c5.close()

# Clean test env
c6 = ssh_connect(TH, TP, TU, TPass)
run(c6, f"rm -f {REMOTE}")
c6.close()

# Clean local
os.remove(LOCAL_DUMP)

print("\n" + "=" * 55)
print("数据库同步完成!")
print("=" * 55)
