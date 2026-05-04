"""验证 schema 变更"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=30)

cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 "
    "-e \""
    "SELECT 'products.payment_timeout_minutes_exists' AS k, COUNT(*) AS v FROM information_schema.columns "
    "WHERE table_schema='bini_health' AND table_name='products' AND column_name='payment_timeout_minutes' "
    "UNION ALL "
    "SELECT 'unified_orders.payment_timeout_minutes_exists', COUNT(*) FROM information_schema.columns "
    "WHERE table_schema='bini_health' AND table_name='unified_orders' AND column_name='payment_timeout_minutes' "
    "UNION ALL "
    "SELECT 'unified_orders.order_timeout_minutes_exists', COUNT(*) FROM information_schema.columns "
    "WHERE table_schema='bini_health' AND table_name='unified_orders' AND column_name='order_timeout_minutes' "
    "UNION ALL "
    "SELECT 'order_items.redemption_code_status_exists', COUNT(*) FROM information_schema.columns "
    "WHERE table_schema='bini_health' AND table_name='order_items' AND column_name='redemption_code_status'"
    "\""
)

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print("STDOUT:")
print(out)
if err:
    print("STDERR:", err)
ssh.close()
