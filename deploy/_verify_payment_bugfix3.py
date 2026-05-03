"""直接调用业务函数验证修复（不走 HTTP，绕过权限）。"""
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
        print(f"[stderr] {err[:1500]}")
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        # 找一个 active 的 admin 账号
        run(client, f"""docker exec {DID}-backend python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    eng = create_async_engine(os.environ['DATABASE_URL'])
    async with eng.begin() as conn:
        rows = (await conn.execute(text(\\"SELECT id, phone, nickname, role, status FROM users WHERE role='admin' AND status='active' LIMIT 5\\"))).fetchall()
        for r in rows:
            print(repr(dict(r._mapping)))
asyncio.run(main())
" """)

        # 找到后用 token 登录测试 list 接口
        run(client, f"""docker exec {DID}-backend python -c "
import asyncio, os, json
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.security import create_access_token
import httpx

async def main():
    eng = create_async_engine(os.environ['DATABASE_URL'])
    async with eng.begin() as conn:
        row = (await conn.execute(text(\\"SELECT id, role FROM users WHERE role='admin' AND status='active' LIMIT 1\\"))).fetchone()
    if not row:
        print('NO ACTIVE ADMIN found')
        return
    print('admin id=', row.id)
    token = create_access_token({{'sub': str(row.id), 'role': row.role}})
    async with httpx.AsyncClient(base_url='http://localhost:8000') as c:
        r = await c.get('/api/admin/payment-channels', headers={{'Authorization': 'Bearer '+token}})
        print('LIST status:', r.status_code)
        if r.status_code == 200:
            data = r.json()
            print('count:', len(data))
            for x in data:
                print(' -', x['channel_code'], 'display=', x['display_name'], 'enabled=', x['is_enabled'], 'complete=', x['is_complete'], 'created_at=', x['created_at'])
        else:
            print('body:', r.text[:600])
asyncio.run(main())
" """)
    finally:
        client.close()


if __name__ == "__main__":
    main()
