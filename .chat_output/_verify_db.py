"""Verify DB schema applied."""
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

cmds = [
    # Check enum on products.fulfillment_type
    f'docker exec {DEPLOY_ID}-db mysql -uroot -proot bini_health -e "SHOW COLUMNS FROM products LIKE \'fulfillment_type\'" 2>&1 | tail -10',
    # Check unified_orders has new columns
    f'docker exec {DEPLOY_ID}-db mysql -uroot -proot bini_health -e "SHOW COLUMNS FROM unified_orders LIKE \'service_address%\'" 2>&1',
    # Same for order_items
    f'docker exec {DEPLOY_ID}-db mysql -uroot -proot bini_health -e "SHOW COLUMNS FROM order_items LIKE \'fulfillment_type\'" 2>&1',
    # check schema_sync logs in backend
    f"docker logs {DEPLOY_ID}-backend 2>&1 | grep -iE 'on_site|service_address|schema|migrat' | tail -30",
]

for c in cmds:
    print(f"\n$ {c}")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=60)
    code = stdout.channel.recv_exit_status()
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err:
        print("STDERR:", err[:500])
    print(f"  exit: {code}")

ssh.close()
