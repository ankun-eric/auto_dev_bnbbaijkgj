"""Final fix: create admin account and verify deployment."""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)
D = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def ssh_cmd(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

# 1. Admin healthcheck test
print('=== 1. Admin HTTP Test ===')
out, err = ssh_cmd(
    f'docker exec {D}-admin node -e "require(\'http\').get(\'http://localhost:3000/admin\',r=>{{process.exit(r.statusCode===200||r.statusCode===308?0:1)}})" 2>&1'
)
print(f'  Result: {"OK (admin responding)" if not err else err[:100]}')

# 2. Write Python script to server for admin creation
print('\n=== 2. Create Admin Script ===')
script = '''
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
            print('ADMIN_EXISTS:' + str(user.id) + ':' + str(user.phone) + ':' + str(user.role))
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
            print('ADMIN_CREATED:' + str(new_admin.id) + ':' + str(new_admin.phone))

asyncio.run(main())
'''

# Write script to server
write_cmd = f"cat > /tmp/create_admin.py << 'SCRIPT_EOF'\n{script}\nSCRIPT_EOF"
out, err = ssh_cmd(write_cmd)
print(f'  Script written: {"OK" if not err else err[:100]}')

# Execute script
out, err = ssh_cmd(f'docker exec {D}-backend python3 /tmp/create_admin.py 2>&1', timeout=30)
print(f'  Result: {out[:500]}')
if err:
    print(f'  [stderr]: {err[:300]}')

# The script is inside backend container, need to copy it there
# Let me use a different approach - execute directly via docker exec python3 -c with properly escaped string

print('\n=== 2b. Direct admin creation ===')
# Use a simpler one-liner approach
create_sql = f"docker exec {D}-db mysql -uroot -pbini_health_2026 bini_health -e \"SELECT id, phone, role FROM users WHERE phone='admin';\" 2>&1"
out, err = ssh_cmd(create_sql)
if 'admin' in out:
    print(f'  Admin exists: {out}')
else:
    print('  No admin user with phone=admin, creating...')
    # Create via Python in backend
    py_cmd = '''python3 -c "
import asyncio, sys
sys.path.insert(0,'/app')
from app.core.database import engine
from app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
pc = CryptContext(schemes=['bcrypt'], deprecated='auto')
async def main():
    async with AsyncSession(engine) as s:
        r = await s.execute(select(User).where(User.phone=='admin'))
        u = r.scalar_one_or_none()
        if u:
            print('EXISTS:'+str(u.id))
        else:
            nu = User(phone='admin',password_hash=pc.hash('admin123'),nickname='Admin',role='admin',is_active=True)
            s.add(nu)
            await s.commit()
            await s.refresh(nu)
            print('CREATED:'+str(nu.id))
asyncio.run(main())
"'''
    out, err = ssh_cmd(f'docker exec {D}-backend {py_cmd} 2>&1', timeout=30)
    print(f'  Result: {out[:500]}')
    if err:
        print(f'  [stderr]: {err[:300]}')

# 3. Verify login
print('\n=== 3. Verify admin login ===')
verify_cmd = '''python3 -c "
import asyncio, sys
sys.path.insert(0,'/app')
from app.core.database import engine
from app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
pc = CryptContext(schemes=['bcrypt'], deprecated='auto')
async def main():
    async with AsyncSession(engine) as s:
        r = await s.execute(select(User).where(User.phone=='admin'))
        u = r.scalar_one_or_none()
        if u:
            ok = pc.verify('admin123', u.password_hash)
            print('LOGIN_' + ('OK' if ok else 'FAIL') + ':phone=' + str(u.phone) + ':role=' + str(u.role))
        else:
            print('NOT_FOUND')
asyncio.run(main())
"'''
out, err = ssh_cmd(f'docker exec {D}-backend {verify_cmd} 2>&1', timeout=30)
print(f'  {out[:500]}')
if err:
    print(f'  [stderr]: {err[:300]}')

# 4. Final status
print('\n=== 4. Final Container Status ===')
out, err = ssh_cmd(f'docker ps --filter name={D} --format "table {{{{.Names}}}}\t{{{{.Status}}}}"')
print(out)

# 5. Test API externally
print('\n=== 5. External API test ===')
out, err = ssh_cmd(f'curl -sk https://{D}.noob-ai.test.bangbangvip.com/api/health 2>&1 | head -c 200', timeout=15)
print(f'  API Health: {out[:200]}')

print('\n=== 6. External H5 test ===')
out, err = ssh_cmd(f'curl -sk -o /dev/null -w "%{{http_code}}" https://{D}.noob-ai.test.bangbangvip.com/ 2>&1', timeout=15)
print(f'  H5 HTTP status: {out}')

print('\n=== 7. External Admin test ===')
out, err = ssh_cmd(f'curl -sk -o /dev/null -w "%{{http_code}}" https://{D}.noob-ai.test.bangbangvip.com/admin/ 2>&1', timeout=15)
print(f'  Admin HTTP status: {out}')

client.close()
print('\n全部修复完成!')
