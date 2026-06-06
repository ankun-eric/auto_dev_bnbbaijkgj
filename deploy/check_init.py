"""Check init and users."""
import paramiko, io

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

OUTF = "C:/auto_output/bnbbaijkgj/check_init_out.txt"
def log(msg):
    with open(OUTF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def run(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: log(f"OUT: {out[:500]}")
    if err: log(f"ERR: {err[:500]}")
    return out, err

open(OUTF, "w").close()

# Check init.sql
log("=== init.sql ===")
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend head -50 /app/init.sql 2>/dev/null || echo 'NO_INIT_SQL'")

# Check backend logs
log("\n=== Backend logs ===")
run("docker logs --tail 30 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1")

# Check users via script
log("\n=== Users ===")
script = '''
import sys; sys.path.insert(0, '/app')
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def q():
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT id, phone, nickname, role FROM users ORDER BY id LIMIT 5"))
        rows = r.fetchall()
        for row in rows:
            print(dict(row._mapping))
asyncio.run(q())
'''
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(script.encode()), '/tmp/check_users.py')
sftp.close()
run("docker cp /tmp/check_users.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/tmp/check_users.py")
run("docker exec -w /app 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 /tmp/check_users.py")

# Check account_identities
log("\n=== Identities ===")
script2 = '''
import sys; sys.path.insert(0, '/app')
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def q():
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT * FROM account_identities LIMIT 5"))
        rows = r.fetchall()
        for row in rows:
            print(dict(row._mapping))
asyncio.run(q())
'''
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(script2.encode()), '/tmp/check_ident.py')
sftp.close()
run("docker cp /tmp/check_ident.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/tmp/check_ident.py")
run("docker exec -w /app 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 /tmp/check_ident.py")

ssh.close()
log("\n=== Done ===")
