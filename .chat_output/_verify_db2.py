"""Verify DB schema applied (with correct password)."""
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DB_PASS = 'bini_health_2026'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def run(cmd):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err and 'Warning' not in err:
        print("STDERR:", err[:500])
    print(f"  exit: {code}")
    return out

cmds = [
    f'docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PASS} bini_health -e "SHOW COLUMNS FROM products LIKE \'fulfillment_type\'"',
    f'docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PASS} bini_health -e "SHOW COLUMNS FROM unified_orders LIKE \'service_address%\'"',
    f'docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PASS} bini_health -e "SHOW COLUMNS FROM order_items LIKE \'fulfillment_type\'"',
    f'docker logs {DEPLOY_ID}-backend 2>&1 | grep -iE "on_site|service_address|schema_sync|sync_" | tail -20',
]

for c in cmds:
    run(c)

ssh.close()
