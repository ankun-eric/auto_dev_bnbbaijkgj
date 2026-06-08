"""创建默认管理员账号 (含phone字段)"""
import paramiko, time, io

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_exec(ssh, cmd, timeout=60):
    print(f"  [CMD] {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return out.strip(), err.strip(), code

print("="*60)
print("创建默认管理员账号")
print("="*60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
print("SSH 连接成功\n")

# 首先查看 User 模型的字段
print(">>> 1. 探测 User 模型...")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c \"import sys; sys.path.insert(0,'/app'); import os; os.chdir('/app'); from app.models.models import User; print([c.name for c in User.__table__.columns])\" 2>&1", timeout=20)
print(f"  User 字段: {out[:500]}")
if err:
    print(f"  STDERR: {err[:500]}")

# ====== 2. 创建管理员账号 ======
print("\n>>> 2. 创建管理员账号...")
# 根据探测到的字段创建账号
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
            return
        
        # 创建账号 - 尝试带所有可能需要的字段
        try:
            user = User(
                username='admin',
                phone='13800000000',
                hashed_password=get_password_hash('admin123'),
                is_admin=True,
                is_active=True,
                full_name='Administrator',
                role='admin'
            )
            db.add(user)
            await db.commit()
            print("ADMIN_CREATED")
        except Exception as e:
            await db.rollback()
            # 尝试不带 role
            try:
                user = User(
                    username='admin',
                    phone='13800000000',
                    hashed_password=get_password_hash('admin123'),
                    is_admin=True,
                    is_active=True,
                    full_name='Administrator'
                )
                db.add(user)
                await db.commit()
                print("ADMIN_CREATED_NO_ROLE")
            except Exception as e2:
                await db.rollback()
                print(f"CREATE_FAIL: {e2}")

asyncio.run(do_admin())
"""
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(admin_script.encode()), "/tmp/admin_v2.py")
sftp.close()
out, err, code = ssh_exec(ssh, f"docker cp /tmp/admin_v2.py {DEPLOY_ID}-backend:/tmp/admin_v2.py 2>&1")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 /tmp/admin_v2.py 2>&1", timeout=30)
print(f"  结果: {out[:500]}")
if err:
    print(f"  STDERR: {err[:500]}")

# ====== 3. 验证登录 ======
print("\n>>> 3. 验证登录...")
# 使用 phone 登录
out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -X POST -H 'Content-Type: application/json' -d '{{\"phone\":\"13800000000\",\"password\":\"admin123\"}}' 2>&1")
print(f"  phone登录: {out[:300]}")

# 也试试 username 登录
out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -X POST -H 'Content-Type: application/json' -d '{{\"username\":\"admin\",\"password\":\"admin123\",\"phone\":\"13800000000\"}}' 2>&1")
print(f"  user+phone登录: {out[:300]}")

print("\n✅ 完成")
ssh.close()
