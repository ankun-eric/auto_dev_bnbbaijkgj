"""[BUGFIX-UO-20260507-001] 查询样本订单实存数据用于根因取证"""
import subprocess
import sys

SSH_HOST = "ubuntu@newbb.test.bangbangvip.com"
DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
SQL = r"""
SELECT
  uo.id, uo.order_no, uo.payment_method, uo.payment_channel_code,
  uo.payment_display_name, uo.status, uo.paid_at, uo.created_at, uo.updated_at
FROM unified_orders uo
WHERE uo.order_no='UO20260507075333421500'\G

SELECT
  oi.id, oi.order_id, oi.product_id, oi.product_name,
  oi.appointment_time, oi.appointment_data
FROM order_items oi
JOIN unified_orders uo ON uo.id = oi.order_id
WHERE uo.order_no='UO20260507075333421500'\G
"""

cmd = [
    "ssh", SSH_HOST,
    "docker exec %s mysql -uroot -pbini_health_2026 bini_health -e \"%s\" 2>/dev/null" % (DB_CONTAINER, SQL),
]
print("[CMD]", " ".join(cmd))
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
print("[STDOUT]")
print(result.stdout)
print("[STDERR]")
print(result.stderr)
print("[RC]", result.returncode)
