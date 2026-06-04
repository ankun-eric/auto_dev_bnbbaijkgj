import paramiko, os, time

TH = "newbb.test.bangbangvip.com"; TP = 22; TU = "ubuntu"; TPass = "Newbang888"
TC = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
TDB = "bini_health"; TDU = "root"; TDP = "bini_health_2026"

PH = "chat.benne-ai.com"; PP = 22; PU = "ubuntu"; PPass = "Benne-ai@#"
PDH = "gz-cdb-nniq1lmp.sql.tencentcdb.com"; PDP = "27082"
PDU = "root"; PDPass = "xiaokang989aab"; PDB = "bini_health"

LOCAL = r"C:\auto_output\bnbbaijkgj\deploy"
DUMP = "bini_health_full.sql"
REMOTE = f"/tmp/{DUMP}"
LOCAL_DUMP = os.path.join(LOCAL, DUMP)

def ssh(h, u, pw, p=22):
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
    if out and len(out) < 500:
        print(f"    {out}")
    if err and len(err) > 2:
        for line in err.split('\n'):
            if line.strip():
                print(f"    [ERR] {line[:200]}")
    return out, err, code

# ===== Step 1: Export with better params =====
print("=" * 55)
print("Step 1: 导出测试环境（完整参数）")
print("=" * 55)
c1 = ssh(TH, TU, TPass)
dump_cmd = (
    f"docker exec {TC} mysqldump "
    f"-u{TDU} -p{TDP} "
    f"--single-transaction --routines --triggers --events "
    f"--complete-insert --skip-add-locks --no-tablespaces "
    f"--set-gtid-purged=OFF "
    f"--databases {TDB} > {REMOTE} 2>/dev/null"
)
out, err, code = run(c1, dump_cmd, t=300)
print(f"  Export: code={code}")
out, err, code = run(c1, f"ls -lh {REMOTE}")
print(f"  Size: {out}")
c1.close()

# ===== Step 2: Download =====
print("\n" + "=" * 55)
print("Step 2: 下载")
print("=" * 55)
c2 = ssh(TH, TU, TPass)
s = c2.open_sftp()
fs = s.stat(REMOTE).st_size
print(f"  远程 {fs/1024/1024:.2f}MB")
s.get(REMOTE, LOCAL_DUMP)
s.close(); c2.close()
print(f"  本地 {os.path.getsize(LOCAL_DUMP)/1024/1024:.2f}MB OK")

# ===== Step 3: Upload =====
print("\n" + "=" * 55)
print("Step 3: 上传到生产环境")
print("=" * 55)
c3 = ssh(PH, PU, PPass)
s3 = c3.open_sftp()
s3.put(LOCAL_DUMP, REMOTE)
s3.close()
run(c3, f"ls -lh {REMOTE}")

# ===== Step 4: Fix collation then import =====
print("\n" + "=" * 55)
print("Step 4: 修复排序规则并导入")
print("=" * 55)

# Fix collation incompatibility
fix_cmd = f"sed -i 's/utf8mb4_0900_ai_ci/utf8mb4_general_ci/g' {REMOTE}"
run(c3, fix_cmd, t=10)
print("  排序规则已替换: utf8mb4_0900_ai_ci -> utf8mb4_general_ci")

import_cmd = (
    f"sudo docker run --rm --network host "
    f"-v {REMOTE}:/dump.sql:ro "
    f"mysql:8.0 "
    f"bash -c 'mysql -h{PDH} -P{PDP} -u{PDU} -p{PDPass} "
    f"{PDB} < /dump.sql' 2>&1"
)
out, err, code = run(c3, import_cmd, t=600)
print(f"  Import code: {code}")

# ===== Step 5: Verify =====
print("\n" + "=" * 55)
print("Step 5: 验证")
print("=" * 55)
verify_script = (
    "import pymysql\n"
    f"conn=pymysql.connect(host='{PDH}',port={PDP},user='{PDU}',password='{PDPass}',database='{PDB}')\n"
    "c=conn.cursor()\n"
    "tables=['merchant_stores','merchant_profiles','merchant_store_memberships','users']\n"
    "for t in tables:\n"
    " c.execute('SELECT COUNT(*) FROM '+t)\n"
    " cnt=c.fetchone()[0]\n"
    " print(t,cnt)\n"
    "conn.close()"
)
with c3.open_sftp() as sf:
    with sf.open("/tmp/v2.py", "w") as f:
        f.write(verify_script)
out, err, code = run(c3, "python3 /tmp/v2.py 2>&1", t=15)
print(out)

# ===== Step 6: Restart backend =====
print("\n" + "=" * 55)
print("Step 6: 重启后端")
print("=" * 55)
run(c3, "sudo docker restart 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1", t=60)
time.sleep(15)
out, err, code = run(c3, "sudo docker ps --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format '{{.Status}}'")
print(f"  Backend: {out}")

# ===== Cleanup =====
run(c3, f"rm -f {REMOTE} /tmp/v2.py")
c3.close()
c4 = ssh(TH, TU, TPass)
run(c4, f"rm -f {REMOTE}")
c4.close()
os.remove(LOCAL_DUMP)

print("\n" + "=" * 55)
print("数据重新同步完成!")
print("=" * 55)
