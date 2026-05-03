"""用现有生产 admin (id=1) 直接 token 验证。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=120):
    print(f"\n>>> running...")
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
        run(client, f"""docker exec {DID}-backend python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.security import create_access_token

async def main():
    eng = create_async_engine(os.environ['DATABASE_URL'])
    # 启用 id=1 这个 admin（如果它被禁用了）+ 也启用 13800050505
    async with eng.begin() as conn:
        await conn.execute(text(\\"UPDATE users SET is_active=1 WHERE id=1 OR phone='13800050505'\\"))
        row = (await conn.execute(text(\\"SELECT id, role, is_active FROM users WHERE id=1\\"))).fetchone()
        print('admin user:', dict(row._mapping))
    token = create_access_token({{'sub': '1', 'role': 'admin'}})
    import httpx
    async with httpx.AsyncClient(base_url='http://localhost:8000') as c:
        r = await c.get('/api/admin/payment-channels', headers={{'Authorization': 'Bearer '+token}})
        print('LIST status:', r.status_code)
        if r.status_code == 200:
            data = r.json()
            print('count:', len(data))
            for x in data:
                print(' ', x['channel_code'], '| display=', x['display_name'], '| enabled=', x['is_enabled'], '| complete=', x['is_complete'], '| created=', x['created_at'])
            # 取一条详情
            r2 = await c.get('/api/admin/payment-channels/wechat_miniprogram', headers={{'Authorization':'Bearer '+token}})
            print('DETAIL status:', r2.status_code)
            print('DETAIL body:', r2.text[:400])
        else:
            print('body:', r.text[:500])
asyncio.run(main())
" """)

        # 看启动日志的支付配置自检
        run(client, f"docker logs {DID}-backend 2>&1 | grep -i '\\[支付配置\\]\\|app.payment_config' | tail -10")
    finally:
        client.close()


if __name__ == "__main__":
    main()
