"""Run DB migration and admin user check post-deployment."""
import paramiko
import sys

HOST = "134.175.97.26"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=30)

def run(title, cmd, timeout=120):
    print(f"\n=== {title} ===")
    print(f"CMD: {cmd[:150]}...")
    i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8', errors='replace')
    err = e.read().decode('utf-8', errors='replace')
    code = o.channel.recv_exit_status()
    print(f"exit={code}")
    if out:
        print(out[:2000])
    if err:
        print("STDERR:", err[:500])
    return out, err, code

# 1. DB migration
run("DB Migration", f"""docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/db_migrate.py && cd /app && PYTHONPATH=/app python /tmp/db_migrate.py' << 'PYEOF'
import asyncio
from app.core.database import engine, Base
async def check():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("create_all done")
asyncio.run(check())
PYEOF""", timeout=120)

# 2. List DB tables
run("DB Tables", f"""docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/db_list.py && cd /app && PYTHONPATH=/app python /tmp/db_list.py' << 'PYEOF'
import asyncio
from app.core.database import engine
from sqlalchemy import text
async def list_tables():
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES"))
        tables = [r[0] for r in result.fetchall()]
        print(f"Total tables: {{len(tables)}}")
        for t in sorted(tables)[:30]:
            print(f"  {{t}}")
asyncio.run(list_tables())
PYEOF""", timeout=60)

# 3. Check admin
out, err, code = run("Admin Check", f"""docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/check_admin.py && cd /app && PYTHONPATH=/app python /tmp/check_admin.py' << 'PYEOF'
import asyncio
from app.core.database import async_session
from sqlalchemy import text
async def check_admin():
    async with async_session() as db:
        r = await db.execute(text("SELECT id, phone, nickname, role FROM users WHERE role='admin' LIMIT 1"))
        row = r.fetchone()
        if row:
            print(f"ADMIN_EXISTS: id={{row[0]}}, phone={{row[1]}}, nickname={{row[2]}}, role={{row[3]}}")
        else:
            print("NO_ADMIN")
asyncio.run(check_admin())
PYEOF""", timeout=30)

if "NO_ADMIN" in out:
    run("Create Admin", f"""docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/create_admin.py && cd /app && PYTHONPATH=/app python /tmp/create_admin.py' << 'PYEOF'
import asyncio
from app.core.database import async_session
from app.models.models import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy import select
async def create_admin():
    async with async_session() as db:
        r = await db.execute(select(User).where(User.role == UserRole.admin))
        user = r.scalar_one_or_none()
        if not user:
            db.add(User(phone="13800000000", nickname="admin", password_hash=get_password_hash("admin123"), role=UserRole.admin, is_superuser=True))
            await db.commit()
            print("Admin created: admin/admin123")
        else:
            print("Admin already exists")
asyncio.run(create_admin())
PYEOF""", timeout=30)

# 4. Health check
run("Health Check", f"curl -s https://{DOMAIN}/api/health", timeout=15)

# 5. BUILD_INFO
run("BUILD_INFO", f"docker exec {DEPLOY_ID}-backend cat /app/BUILD_INFO", timeout=15)

ssh.close()
print("\n=== ALL DONE ===")
