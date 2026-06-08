import paramiko, re

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("chat.benne-ai.com", port=22, username="ubuntu", password="Benne-ai@#", timeout=30)

def run(cmd, timeout=60):
    print("> " + cmd[:120])
    _, o, e = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    result = out + err
    result = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', result)
    result = re.sub(r'\x1b\[[?]\d+[hl]', '', result)
    result = re.sub(r'\x1b\[[=]', '', result)
    if result.strip(): print(result.strip()[:500])
    return result

# 将脚本文件写入服务器
print("=== 写入检查脚本 ===")
script = '''import sys
sys.path.insert(0, "/app")
import asyncio
from app.core.database import async_session
from app.models.models import User
from sqlalchemy import select

async def main():
    async with async_session() as db:
        r = await db.execute(select(User).where(User.is_superuser == True).limit(10))
        users = r.scalars().all()
        print("superusers=" + str(len(users)))
        for u in users:
            print("id=" + str(u.id) + " phone=" + str(u.phone) + " nickname=" + str(u.nickname))

asyncio.run(main())
'''

# 写入 host 文件
cmd = "cat > /tmp/check_superuser.py << 'PYEOF'\n" + script + "\nPYEOF"
run(cmd)

# docker cp 到容器
run("docker cp /tmp/check_superuser.py " + DEPLOY_ID + "-backend:/tmp/check_superuser.py 2>&1")

# 执行
print("\n=== 执行检查 ===")
result = run("docker exec " + DEPLOY_ID + "-backend python /tmp/check_superuser.py 2>&1")

# 如果没有 superuser，创建
if "superusers=0" in result:
    print("\n=== 创建超级用户 ===")
    create_script = '''import sys
sys.path.insert(0, "/app")
import asyncio
from app.core.database import async_session
from app.models.models import User
from app.core.security import get_password_hash

async def main():
    async with async_session() as db:
        u = User(
            phone="admin",
            password_hash=get_password_hash("admin123"),
            nickname="管理员",
            is_superuser=True
        )
        db.add(u)
        await db.commit()
        print("SUPERUSER_CREATED id=" + str(u.id))

asyncio.run(main())
'''
    cmd2 = "cat > /tmp/create_superuser.py << 'PYEOF'\n" + create_script + "\nPYEOF"
    run(cmd2)
    run("docker cp /tmp/create_superuser.py " + DEPLOY_ID + "-backend:/tmp/create_superuser.py 2>&1")
    run("docker exec " + DEPLOY_ID + "-backend python /tmp/create_superuser.py 2>&1")
    print("  超级用户已创建: admin / admin123")
elif "superusers=" in result:
    print("  超级用户已存在")

ssh.close()
print("\n完成")
