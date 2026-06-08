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
    if result.strip():
        print(result.strip()[:500])
    return result

# 查询superusers
cmd = 'docker exec ' + DEPLOY_ID + '-backend python -c "'
cmd += 'import asyncio; '
cmd += 'from app.core.database import async_session; '
cmd += 'from app.models.models import User; '
cmd += 'from sqlalchemy import select; '
cmd += 'async def f(): '
cmd += '  async with async_session() as db: '
cmd += '    r=await db.execute(select(User).where(User.is_superuser==True).limit(5)); '
cmd += '    users=r.scalars().all(); '
cmd += '    print(\"superusers=\"+str(len(users))); '
cmd += '    for u in users: '
cmd += '      print(\"id=\"+str(u.id)+\" phone=\"+str(u.phone)+\" nickname=\"+str(u.nickname)); '
cmd += 'asyncio.run(f())'
cmd += '" 2>&1'

print("=== 超级用户 ===")
result = run(cmd, timeout=15)

# 如果无superuser，创建一个
if "superusers=0" in result:
    print("\n=== 创建超级用户 ===")
    cmd2 = 'docker exec ' + DEPLOY_ID + '-backend python -c "'
    cmd2 += 'import asyncio; '
    cmd2 += 'from app.core.database import async_session; '
    cmd2 += 'from app.models.models import User; '
    cmd2 += 'from app.core.security import get_password_hash; '
    cmd2 += 'async def f(): '
    cmd2 += '  async with async_session() as db: '
    cmd2 += '    u=User(phone=\"admin\",password_hash=get_password_hash(\"admin123\"),nickname=\"管理员\",is_superuser=True); '
    cmd2 += '    db.add(u); await db.commit(); '
    cmd2 += '    print(\"SUPERUSER_CREATED\"); '
    cmd2 += 'asyncio.run(f())'
    cmd2 += '" 2>&1'
    run(cmd2, timeout=15)

ssh.close()
print("\n完成")
