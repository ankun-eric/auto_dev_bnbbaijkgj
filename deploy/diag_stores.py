import paramiko

PH = "chat.benne-ai.com"; PU = "ubuntu"; PPass = "Benne-ai@#"
PDH = "gz-cdb-nniq1lmp.sql.tencentcdb.com"; PDP = "27082"
PDU = "root"; PDPass = "xiaokang989aab"; PDB = "bini_health"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(PH, port=22, username=PU, password=PPass, timeout=15)

def run(cmd, t=15):
    si, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors='replace').strip()

# 1. Database query
print("=== 数据库: 门店相关表 ===")
sql = (
    "import pymysql; "
    f"conn=pymysql.connect(host='{PDH}',port={PDP},user='{PDU}',password='{PDPass}',database='{PDB}'); "
    "c=conn.cursor(); "
    "tables=['merchant_stores','merchant_profiles','merchant_store_memberships','merchant_categories']; "
    "for t in tables: "
    "  c.execute('SELECT COUNT(*) FROM '+t); "
    "  cnt=c.fetchone()[0]; "
    "  print(t,cnt); "
    "  if cnt>0: "
    "    c.execute('SELECT * FROM '+t+' LIMIT 3'); "
    "    rows=c.fetchall(); "
    "    for r in rows: print('  ',r[:5]); "
    "conn.close()"
)
out = run(f"python3 -c '{sql}' 2>&1", t=15)
print(out)

# 2. Backend logs
print("\n=== 后端日志（最近20行）===")
out = run("sudo docker logs --tail=20 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1")
print(out[-1500:])

# 3. Test API
print("\n=== API测试 ===")
apis = [
    "/api/admin/stores",
    "/api/admin/merchants",
    "/api/merchant/stores",
]
for api in apis:
    out = run(f"curl -sk https://localhost{api} 2>&1 | python3 -c 'import sys; d=sys.stdin.read(); print(d[:300])' 2>&1", t=15)
    print(f"  {api}: {out[:300]}")

c.close()
