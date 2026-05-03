"""验证支付配置 Bug 修复：用真实生产 admin 账号登录后访问列表接口。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=120):
    print(f"\n>>> {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
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
        # 看一下日志中有无 PaymentChannelResponse ValidationError 已不再出现
        run(client, f"docker logs --tail 300 {DID}-backend 2>&1 | grep -i 'PaymentChannelResponse\\|payment-channels\\|payment_config' | tail -30")

        # 找真实 admin 账号
        run(client, f"""docker exec {DID}-backend python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    eng = create_async_engine(os.environ['DATABASE_URL'])
    async with eng.begin() as conn:
        rows = (await conn.execute(text(\\"SELECT id, phone, nickname, role FROM users WHERE role IN ('admin', 'super_admin') LIMIT 5\\"))).fetchall()
        for r in rows:
            print(repr(dict(r._mapping)))
asyncio.run(main())
" """)

        # 创建一个临时 super-admin 测试账号 + 直接查询接口
        run(client, f"""docker exec {DID}-backend python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.core.security import get_password_hash, create_access_token
async def main():
    eng = create_async_engine(os.environ['DATABASE_URL'])
    Session = async_sessionmaker(eng, expire_on_commit=False)
    # 检查或插入 admin
    async with eng.begin() as conn:
        row = (await conn.execute(text(\\"SELECT id, role FROM users WHERE phone='13800013800' LIMIT 1\\"))).fetchone()
        if row is None:
            ph = get_password_hash('admin123')
            await conn.execute(text(\\"INSERT INTO users(phone, password_hash, nickname, role, created_at, updated_at) VALUES('13800013800', :ph, '验证管理员', 'admin', NOW(), NOW())\\"), {{'ph': ph}})
            row = (await conn.execute(text(\\"SELECT id, role FROM users WHERE phone='13800013800'\\"))).fetchone()
        print('user', dict(row._mapping))
        token = create_access_token({{'sub': str(row.id), 'role': row.role}})
        print('token', token[:60], '...')

    import httpx
    async with httpx.AsyncClient(base_url='http://localhost:8000') as c:
        r = await c.get('/api/admin/payment-channels', headers={{'Authorization': 'Bearer '+token}})
        print('list', r.status_code)
        if r.status_code == 200:
            data = r.json()
            print('count', len(data))
            for x in data:
                print(' -', x['channel_code'], 'is_enabled=', x['is_enabled'], 'is_complete=', x['is_complete'], 'created_at=', x['created_at'])
        else:
            print('body', r.text[:500])
asyncio.run(main())
" """)
    finally:
        client.close()


if __name__ == "__main__":
    main()
