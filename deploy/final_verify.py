import paramiko, base64, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run_sql(sql, db="bini_health"):
    enc = base64.b64encode(sql.encode('utf-8')).decode('ascii')
    cmd = "echo %s | base64 -d | docker exec -i 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -p'bini_health_2026' %s 2>/dev/null" % (enc, db)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode('utf-8', errors='replace').strip()

tables = ['users', 'chat_messages', 'chat_sessions', 'products', 'merchant_stores',
          'unified_orders', 'coupons', 'notifications', 'articles', 'comments']
print("Key table row counts (test env):")
print("=" * 50)
for t in tables:
    result = run_sql("SELECT COUNT(*) FROM `"+t+"`")
    try:
        cnt = result.split('\n')[-1].strip()
    except:
        cnt = '?'
    print("  %-30s: %6s rows" % (t, cnt))

result = run_sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='bini_health'")
try:
    total = result.split('\n')[-1].strip()
except:
    total = '?'
print("\n  Total tables in test db: %s" % total)

ssh.close()
print("\nDone!")
