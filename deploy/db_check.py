import paramiko, re

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("chat.benne-ai.com", port=22, username="ubuntu", password="Benne-ai@#", timeout=30)

def run(cmd, timeout=60):
    print(f"> {cmd[:120]}")
    _, o, e = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    result = out + err
    result = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', result)
    result = re.sub(r'\x1b\[[?]\d+[hl]', '', result)
    result = re.sub(r'\x1b\[[=]', '', result)
    if result.strip():
        print(result.strip()[:400])
    return out + err

print("=== 检查表 ===")
run(f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import inspect
async def f():
    async with engine.connect() as c:
        def g(conn):
            insp=inspect(conn)
            tables=insp.get_table_names()
            print('table_count='+str(len(tables)))
            print('tables='+','.join(tables[:20]))
        await c.run_sync(g)
asyncio.run(f())
" 2>&1''', timeout=30)

print("\n=== 迁移 ===")
run(f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import engine, Base
async def f():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('MIGRATE_OK')
asyncio.run(f())
" 2>&1''', timeout=30)

print("\n=== 账号 ===")
result = run(f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import async_session
from app.models.models import User
from sqlalchemy import select
async def f():
    async with async_session() as db:
        r=await db.execute(select(User).where(User.username=='admin'))
        u=r.scalar_one_or_none()
        print('ADMIN_EXISTS' if u else 'ADMIN_NOT_FOUND')
asyncio.run(f())
" 2>&1''', timeout=15)

if 'ADMIN_NOT_FOUND' in result:
    print("\n=== 创建账号 ===")
    run(f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import async_session
from app.models.models import User
from app.core.security import get_password_hash
async def f():
    async with async_session() as db:
        user=User(username='admin',hashed_password=get_password_hash('admin123'),is_admin=True)
        db.add(user)
        await db.commit()
        print('ADMIN_CREATED')
asyncio.run(f())
" 2>&1''', timeout=15)

ssh.close()
print("\n完成!")
