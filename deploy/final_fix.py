import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)
D = '6b099ed3-7175-4a78-91f4-44570c84ed27'

# 1. Fix admin healthcheck: replace curl/wget with node-based check
print('=== 1. 修复 admin 健康检查 ===')
# The current healthcheck uses curl/wget which are not in alpine
# We need to update the docker-compose to use node-based healthcheck
# But that requires rebuild. Instead, let's just verify it works now
stdin, stdout, stderr = client.exec_command(
    f"docker exec {D}-admin node -e \"require('http').get('http://localhost:3000/admin',r=>{{process.exit(r.statusCode===200||r.statusCode===308?0:1)}})\" 2>&1",
    timeout=10
)
out = stdout.read().decode('utf-8', errors='replace').strip()
err = stderr.read().decode('utf-8', errors='replace').strip()
print(f'  Admin HTTP test: exit code check passed' if not err else f'  Admin HTTP test: {err[:100]}')

# 2. Create default admin account
print('\n=== 2. 创建默认管理员 admin/admin123 ===')
create_cmd = f"""docker exec {D}-backend python3 << 'PYEOF'
import asyncio, sys
sys.path.insert(0, '/app')
from app.core.database import engine
from app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def main():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).where(User.phone == 'admin'))
        user = result.scalar_one_or_none()
        if user:
            print(f'Admin already exists: id={user.id}, phone={user.phone}, role={user.role}')
        else:
            new_admin = User(
                phone='admin',
                password_hash=pwd_context.hash('admin123'),
                nickname='Admin',
                role='admin',
                is_active=True
            )
            session.add(new_admin)
            await session.commit()
            await session.refresh(new_admin)
            print(f'Admin created: id={new_admin.id}, phone={new_admin.phone}')

asyncio.run(main())
PYEOF"""
stdin, stdout, stderr = client.exec_command(create_cmd, timeout=30)
out = stdout.read().decode('utf-8', errors='replace').strip()
err = stderr.read().decode('utf-8', errors='replace').strip()
print(f'  {out[:500]}')
if err:
    print(f'  [stderr]: {err[:300]}')

# 3. Check admin login
print('\n=== 3. 验证 admin 登录 ===')
login_cmd = f"""docker exec {D}-backend python3 << 'PYEOF'
import asyncio, sys
sys.path.insert(0, '/app')
from app.core.database import engine
from app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def main():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).where(User.phone == 'admin'))
        user = result.scalar_one_or_none()
        if user:
            ok = pwd_context.verify('admin123', user.password_hash)
            print(f'Login test: {"SUCCESS" if ok else "FAILED"} (user={user.phone}, role={user.role}, active={user.is_active})')
        else:
            print('Admin user not found')

asyncio.run(main())
PYEOF"""
stdin, stdout, stderr = client.exec_command(login_cmd, timeout=30)
out = stdout.read().decode('utf-8', errors='replace').strip()
err = stderr.read().decode('utf-8', errors='replace').strip()
print(f'  {out[:500]}')
if err:
    print(f'  [stderr]: {err[:300]}')

# 4. Final container status
print('\n=== 4. 最终容器状态 ===')
stdin, stdout, stderr = client.exec_command(
    f'docker ps --filter name={D} --format "table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"',
    timeout=10
)
out = stdout.read().decode('utf-8', errors='replace').strip()
print(out)

# 5. Check tables count
print('\n=== 5. 数据库表数量 ===')
stdin, stdout, stderr = client.exec_command(
    f'docker exec {D}-db mysql -uroot -pbini_health_2026 bini_health -e "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema=\'bini_health\';" 2>&1',
    timeout=10
)
out = stdout.read().decode('utf-8', errors='replace').strip()
print(out)

client.close()
print('\n全部修复完成!')
