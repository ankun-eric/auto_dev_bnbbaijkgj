"""[订单核销码状态与未支付超时治理 v1.0] 数据清洗结果验证"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=30)

# 进入 backend 容器，用 python 直接查表
cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 "
    "-e \"SELECT 'DIRTY_LEFT_AFTER_MIGRATION=' AS k, COUNT(*) AS v FROM bini_health.order_items oi "
    "JOIN bini_health.unified_orders uo ON uo.id=oi.order_id "
    "WHERE uo.status='cancelled' AND oi.redemption_code_status='active' UNION ALL "
    "SELECT 'TOTAL_CANCELLED_ORDERS=', COUNT(*) FROM bini_health.unified_orders WHERE status='cancelled' UNION ALL "
    "SELECT 'TOTAL_ORDER_ITEMS=', COUNT(*) FROM bini_health.order_items;\""
)

# 把检查脚本上传到容器临时目录
script = """
import asyncio
from sqlalchemy import text
from app.core.database import async_session

async def main():
    async with async_session() as s:
        r = await s.execute(text(
            "SELECT COUNT(*) FROM order_items oi "
            "JOIN unified_orders uo ON uo.id=oi.order_id "
            "WHERE uo.status='cancelled' AND oi.redemption_code_status='active'"
        ))
        cnt = r.scalar()
        print("DIRTY_LEFT_AFTER_MIGRATION=" + str(cnt))

        # 总览：分别按 status / redemption_code_status 分布
        r2 = await s.execute(text(
            "SELECT uo.status, oi.redemption_code_status, COUNT(*) "
            "FROM order_items oi JOIN unified_orders uo ON uo.id=oi.order_id "
            "GROUP BY uo.status, oi.redemption_code_status "
            "ORDER BY uo.status, oi.redemption_code_status"
        ))
        print("DIST:")
        for row in r2.all():
            print(" ", row[0], "/", row[1], "->", row[2])

asyncio.run(main())
"""

# 写到本地临时文件再 SFTP 到服务器
sftp = ssh.open_sftp()
import io
sftp.putfo(io.BytesIO(script.encode("utf-8")), "/tmp/_dirty.py")
ssh.exec_command("docker cp /tmp/_dirty.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/tmp/_dirty.py")
import time; time.sleep(2)
sftp.close()

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print("STDOUT:", out)
print("STDERR:", err)
ssh.close()
