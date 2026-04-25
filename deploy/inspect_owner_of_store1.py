"""[2026-04-26] 看 store_id=1 当前 owner 是谁。"""
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"; DB_PASS="bini_health_2026"
DB_CONT=f"{DEPLOY_ID}-db"
def run(c,cmd):
    print(f"\n$ {cmd}", flush=True)
    _i,o,e=c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8","replace"))
    err=e.read().decode("utf-8","replace")
    if err.strip(): print("ERR:", err)
def mysql(c, sql):
    q = sql.replace('"','\\"')
    run(c, f'docker exec {DB_CONT} sh -c "mysql -uroot -p{DB_PASS} bini_health -e \\"{q}\\"" 2>&1 | head -40')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,22,USER,PASS,timeout=30)
try:
    mysql(c, "SELECT msm.id, msm.user_id, u.phone, u.nickname, msm.member_role, msm.role_code, msm.store_id, ms.store_name FROM merchant_store_memberships msm JOIN users u ON u.id=msm.user_id LEFT JOIN merchant_stores ms ON ms.id=msm.store_id WHERE msm.store_id=1 ORDER BY msm.id;")
    mysql(c, "SELECT id, store_name, store_code FROM merchant_stores ORDER BY id;")
    mysql(c, "SELECT membership_id, module_code FROM merchant_store_permissions WHERE membership_id=1 ORDER BY id;")
finally:
    c.close()
