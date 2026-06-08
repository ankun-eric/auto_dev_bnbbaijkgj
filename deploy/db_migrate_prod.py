#!/usr/bin/env python3
"""数据库迁移和账号修复"""
import paramiko, time, re

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("chat.benne-ai.com", port=22, username="ubuntu", password="Benne-ai@#", timeout=30)

def run(cmd, timeout=60):
    print(f"  > {cmd[:150]}")
    _, o, e = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    result = out + err
    result = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', result)
    result = re.sub(r'\x1b\[[?]\d+[hl]', '', result)
    result = re.sub(r'\x1b\[[=]', '', result)
    if len(result) > 500:
        result = result[:250] + "\n...(截断)...\n" + result[-150:]
    if result.strip():
        print(result.strip())
    return result

print("=" * 60)
print("数据库迁移 + 账号检查")
print("=" * 60)

# 1. 测试数据库连接
print("\n[1] 测试数据库连接...")
run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.core.database import engine; print('engine_ok')\" 2>&1", timeout=15)

# 2. 检查表
print("\n[2] 检查现有表...")
run(f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from app.core.database import engine; from sqlalchemy import inspect; async def check(): async with engine.connect() as c: def sync_check(conn): insp=inspect(conn); tables=insp.get_table_names(); print(f'tables={len(tables)}'); print(','.join(tables[:20])); return tables; return await c.run_sync(sync_check); asyncio.run(check())\" 2>&1", timeout=30)

# 3. 执行增量迁移
print("\n[3] 执行增量迁移...")
migrate_cmd = f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import engine, Base

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('MIGRATE_OK')

asyncio.run(migrate())
" 2>&1'''
run(migrate_cmd, timeout=30)

# 4. 检查默认账号
print("\n[4] 检查默认账号 admin...")
check_cmd = f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import async_session
from app.models.models import User
from sqlalchemy import select

async def check_admin():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == 'admin'))
        user = result.scalar_one_or_none()
        if user:
            print('ADMIN_EXISTS')
        else:
            print('ADMIN_NOT_FOUND')

asyncio.run(check_admin())
" 2>&1'''
result = run(check_cmd, timeout=15)

# 5. 如果账号不存在则创建
if 'ADMIN_NOT_FOUND' in result:
    print("\n[5] 创建默认账号 admin/admin123...")
    create_cmd = f'''docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from app.core.database import async_session
from app.models.models import User
from app.core.security import get_password_hash

async def create_admin():
    async with async_session() as db:
        user = User(
            username='admin',
            hashed_password=get_password_hash('admin123'),
            is_admin=True
        )
        db.add(user)
        await db.commit()
        print('ADMIN_CREATED')

asyncio.run(create_admin())
" 2>&1'''
    run(create_cmd, timeout=15)
else:
    print("  默认账号已存在，无需创建")

# 最终状态
print("\n" + "=" * 60)
print("完成!")
print("生产环境: https://chat.benne-ai.com")
print("管理后台: https://chat.benne-ai.com/admin/")
print("默认账号: admin / admin123")

ssh.close()
