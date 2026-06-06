import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)
D = '6b099ed3-7175-4a78-91f4-44570c84ed27'

cmds = [
    ('admin健康详情', f'docker inspect {D}-admin --format "{{{{json .State.Health}}}}"'),
    ('admin wget测试', f'docker exec {D}-admin wget -qO- http://localhost:3000/admin 2>&1'),
    ('admin node测试', f"docker exec {D}-admin node -e \"const http=require('http');http.get('http://localhost:3000/admin',r=>{{console.log(r.statusCode)}})\" 2>&1"),
    ('db已有admin', f'docker exec {D}-db mysql -uroot -pbini_health_2026 bini_health -e "SELECT id,phone,nickname,role,is_active FROM users WHERE phone=\'admin\' OR nickname=\'Admin\' LIMIT 5;" 2>&1'),
    ('所有users', f'docker exec {D}-db mysql -uroot -pbini_health_2026 bini_health -e "SELECT id,phone,nickname,role,is_active FROM users LIMIT 10;" 2>&1'),
]

for name, cmd in cmds:
    print(f'\n=== {name} ===')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(out[:1000] or '(空)')
    if err:
        print(f'[stderr]: {err[:300]}')

# Try to create admin via Python in backend
print('\n=== 创建admin账号 ===')
create_cmd = f"""docker exec {D}-backend python3 -c "
import asyncio, sys
sys.path.insert(0, '/app')
from app.core.database import engine, get_session
from app.models.models import User
from sqlalchemy import select

async def main():
    async for session in get_session():
        result = await session.execute(select(User).where(User.phone == 'admin'))
        user = result.scalar_one_or_none()
        if user:
            print(f'Admin exists: id={{user.id}}, phone={{user.phone}}, role={{user.role}}')
        else:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
            new_admin = User(
                phone='admin',
                password_hash=pwd_context.hash('admin123'),
                nickname='Admin',
                role='admin',
                is_active=True
            )
            session.add(new_admin)
            await session.commit()
            print(f'Admin created: id={{new_admin.id}}')
        break

asyncio.run(main())
" 2>&1"""
stdin, stdout, stderr = client.exec_command(create_cmd, timeout=30)
out = stdout.read().decode('utf-8', errors='replace').strip()
err = stderr.read().decode('utf-8', errors='replace').strip()
print(out[:500] or '(空)')
if err:
    print(f'[stderr]: {err[:300]}')

client.close()
print('\nDone.')
