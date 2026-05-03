"""第二次更详细的检查：拿完整堆栈和 DB 实际数据。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        # 1) 找到 db 容器的 mysql 凭证
        run(client, f"cd /home/ubuntu/{DID} && grep -A3 'MYSQL_' docker-compose.yml | head -30")
        # 2) 看 backend 完整最近日志
        run(client, f"docker logs --tail 200 {DID}-backend 2>&1 | grep -A 15 'PaymentChannelResponse\\|payment_channels' | tail -80")
        # 3) 找到 backend 容器的 DATABASE_URL
        run(client, f"docker exec {DID}-backend printenv | grep -i 'database_url\\|mysql' | head -5")
        # 4) 找一个 mysql 通用账号
        run(client, f"docker exec {DID}-db cat /etc/mysql/conf.d/zz-bini.cnf 2>/dev/null || docker exec {DID}-db ls /etc/mysql/conf.d/ 2>/dev/null")
        # 5) 用 backend 中的 DB URL 直接查（用 python）
        run(client, """docker exec %s-backend python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    url = os.environ['DATABASE_URL']
    eng = create_async_engine(url)
    async with eng.begin() as conn:
        rows = (await conn.execute(text('SELECT id, channel_code, channel_name, display_name, is_enabled, is_complete, sort_order, created_at, updated_at, last_test_at, last_test_ok FROM payment_channels'))).fetchall()
        for r in rows:
            print(repr(dict(r._mapping)))
asyncio.run(main())
" """ % DID)
    finally:
        client.close()


if __name__ == "__main__":
    main()
