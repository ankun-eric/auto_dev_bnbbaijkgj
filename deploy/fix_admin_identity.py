"""Fix admin identity - add missing account_identity for admin user."""
import paramiko, io

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

def run(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(f"OUT: {out[:500]}")
    if err: print(f"ERR: {err[:500]}")
    return out, err

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# Add admin identity
script = '''
import sys; sys.path.insert(0, '/app')
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def fix():
    async with engine.begin() as conn:
        # Check if admin has identity
        r = await conn.execute(text(
            "SELECT id FROM account_identities WHERE user_id=1 AND identity_type='admin'"
        ))
        existing = r.fetchone()
        if existing:
            print(f"Admin identity already exists: {existing}")
        else:
            await conn.execute(text(
                "INSERT INTO account_identities (user_id, identity_type, status) VALUES (1, 'user', 'active')"
            ))
            print("Admin identity created")
        
        # Verify
        r = await conn.execute(text(
            "SELECT * FROM account_identities WHERE user_id=1"
        ))
        for row in r.fetchall():
            print(dict(row._mapping))

asyncio.run(fix())
'''
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(script.encode()), '/tmp/fix_admin.py')
sftp.close()
run(f"docker cp /tmp/fix_admin.py {DEPLOY_ID}-backend:/tmp/fix_admin.py")
run(f"docker exec {DEPLOY_ID}-backend python3 /tmp/fix_admin.py")

# Test login again
print("\n=== Test Login ===")
test_script = '''
import urllib.request, json
data = json.dumps({"phone":"13800000000","password":"admin123"}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/login', data=data,
    headers={'Content-Type':'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f"Login OK: status={resp.status}")
    print(resp.read().decode()[:300])
except urllib.error.HTTPError as e:
    print(f"Login HTTP {e.code}: {e.read().decode()[:300]}")
'''
sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(test_script.encode()), '/tmp/test_login.py')
sftp.close()
run(f"docker cp /tmp/test_login.py {DEPLOY_ID}-backend:/tmp/test_login.py")
run(f"docker exec {DEPLOY_ID}-backend python3 /tmp/test_login.py")

ssh.close()
