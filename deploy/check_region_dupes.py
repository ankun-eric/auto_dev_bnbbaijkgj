"""检查 brain_game_regions 表中是否有重复的省市区街道数据"""
import paramiko
import sys

HOST = "134.175.97.26"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=30)

def run(title, cmd, timeout=120):
    print(f"\n=== {title} ===")
    i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8', errors='replace')
    err = e.read().decode('utf-8', errors='replace')
    code = o.channel.recv_exit_status()
    print(f"exit={code}")
    if out:
        print(out)
    if err:
        print("STDERR:", err[:500])
    return out, err, code

# 查询 brain_game_regions 表结构和重复数据
sql = """
import pymysql
import os

db_url = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:bini_health_2026@localhost:3306/bini_health')
parts = db_url.replace('mysql+aiomysql://', '').replace('mysql+pymysql://', '')
auth, rest = parts.split('@')
user, pwd = auth.split(':')
host_port, db = rest.split('/')
if ':' in host_port:
    host, port = host_port.split(':')
else:
    host, port = host_port, '3306'

conn = pymysql.connect(host=host, port=int(port), user=user, password=pwd, database=db, charset='utf8mb4')
c = conn.cursor()

print('=== 各级别统计 ===')
c.execute("SELECT level, COUNT(*) as cnt FROM brain_game_regions GROUP BY level ORDER BY FIELD(level, 'province','city','district','street')")
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]} 条')

print()
print('=== 各层级数据样例 ===')
for lv in ['province', 'city', 'district', 'street']:
    c.execute("SELECT id, adcode, name, parent_adcode FROM brain_game_regions WHERE level=%s LIMIT 5", (lv,))
    rows = c.fetchall()
    print(f'--- {lv} (前5条) ---')
    for r in rows:
        print(f'  #{r[0]} adcode={r[1]} name={r[2]} parent={r[3]}')

print()
print('=== 同名同级别重复 ===')
c.execute("SELECT level, name, COUNT(*) as cnt, GROUP_CONCAT(id) as ids FROM brain_game_regions GROUP BY level, name HAVING cnt > 1 ORDER BY cnt DESC")
dupes = c.fetchall()
if dupes:
    for row in dupes:
        print(f'  [{row[0]}] {row[1]}: {row[2]} 条, IDs: {row[3]}')
    print(f'共 {len(dupes)} 组重复')
else:
    print('  无重复')

print()
print('=== 同名+同级别+同父级重复（真正重复） ===')
c.execute("SELECT level, name, parent_adcode, COUNT(*) as cnt, GROUP_CONCAT(id) as ids FROM brain_game_regions GROUP BY level, name, parent_adcode HAVING cnt > 1 ORDER BY cnt DESC")
dupes2 = c.fetchall()
if dupes2:
    for row in dupes2:
        print(f'  [{row[0]}] {row[1]} (parent={row[2]}): {row[3]} 条, IDs: {row[4]}')
    print(f'共 {len(dupes2)} 组重复')
else:
    print('  无重复')

c.close()
conn.close()
"""

cmd = f"""docker exec -i {DEPLOY_ID}-backend sh -c 'python3 /app/../tmp_check.py' << 'PYEOF'
{sql}
PYEOF
"""

# 先把脚本传进去
upload_cmd = f"""docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp_check.py' << 'PYEOF'
{sql}
PYEOF
"""
run("上传检查脚本", upload_cmd)
out, err, code = run("执行检查", f"docker exec {DEPLOY_ID}-backend python3 /tmp_check.py 2>&1")
if code != 0:
    print("=== 完整输出 ===")
    print(out)
    print("=== STDERR ===")
    print(err)

ssh.close()
