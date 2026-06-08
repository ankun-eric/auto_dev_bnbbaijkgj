"""数据库迁移(异步引擎) + 默认账号"""
import paramiko, time, io

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_exec(ssh, cmd, timeout=60):
    print(f"  [CMD] {cmd[:150]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return out.strip(), err.strip(), code

print("="*60)
print("数据库迁移(异步引擎) + 默认账号")
print("="*60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
print("SSH 连接成功\n")

# ====== 1. 检查数据库连接类型 ======
print(">>> 1. 检查数据库引擎...")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c \"import sys; sys.path.insert(0,'/app'); import os; os.chdir('/app'); from app.core.database import engine; print(type(engine).__name__)\" 2>&1", timeout=20)
print(f"  引擎类型: {out[:200]}")

# ====== 2. 通过文件执行异步 create_all ======
print("\n>>> 2. 异步 create_all...")
migrate_script_content = """import asyncio, sys
sys.path.insert(0, "/app")
import os
os.chdir("/app")

async def do_migrate():
    from app.core.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("MIGRATE_OK")

asyncio.run(do_migrate())
"""
# 上传脚本
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(migrate_script_content.encode()), "/tmp/migrate_db.py")
sftp.close()

# 复制到容器并执行
out, err, code = ssh_exec(ssh, f"docker cp /tmp/migrate_db.py {DEPLOY_ID}-backend:/tmp/migrate_db.py 2>&1")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 /tmp/migrate_db.py 2>&1", timeout=30)
print(f"  migrate: {out[:300]}")
if err:
    print(f"  STDERR: {err[:300]}")

# ====== 3. 默认账号 ======
print("\n>>> 3. 默认账号检查与创建...")
admin_script = """import asyncio, sys
sys.path.insert(0, "/app")
import os
os.chdir("/app")

async def do_admin():
    from app.core.database import SessionLocal
    from app.models.models import User
    from app.core.security import get_password_hash
    from sqlalchemy import select
    
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.username == 'admin'))
        existing = result.scalars().first()
        if existing:
            print("ADMIN_EXISTS")
        else:
            user = User(
                username='admin',
                hashed_password=get_password_hash('admin123'),
                is_admin=True,
                is_active=True,
                full_name='Administrator'
            )
            db.add(user)
            await db.commit()
            print("ADMIN_CREATED")

asyncio.run(do_admin())
"""
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(admin_script.encode()), "/tmp/admin_init.py")
sftp.close()
out, err, code = ssh_exec(ssh, f"docker cp /tmp/admin_init.py {DEPLOY_ID}-backend:/tmp/admin_init.py 2>&1")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 /tmp/admin_init.py 2>&1", timeout=30)
print(f"  结果: {out[:300]}")
if err:
    print(f"  STDERR: {err[:300]}")

# ====== 4. 验证 ======
print("\n>>> 4. 验证...")
# API测试
out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -X POST -H 'Content-Type: application/json' -d '{{\"username\":\"admin\",\"password\":\"admin123\"}}' 2>&1")
print(f"  登录API: {out[:300]}")

# 表数量
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c \"import asyncio,sys; sys.path.insert(0,'/app'); import os; os.chdir('/app'); async def f(): from app.core.database import engine; async with engine.connect() as c: r=await c.run_sync(lambda x: x.dialect.get_table_names(x, None)); print(len(r)); asyncio.run(f())\" 2>&1", timeout=30)
print(f"  表数量: {out[:100]}")

print("\n✅ 完成")
ssh.close()
