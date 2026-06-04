import paramiko, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=15)

# Check backend store API by calling it directly in the container
checks = [
    # 1. Direct SQL in backend container
    '''sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c "
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
try:
    rows = db.execute(text('SELECT id, store_name, user_id FROM merchant_stores')).fetchall()
    print('merchant_stores count:', len(rows))
    for r in rows:
        print(f'  id={r[0]} name={r[1][:20]}')
finally:
    db.close()
" 2>&1''',

    # 2. Check backend logs for recent store API calls
    '''sudo docker logs --tail=30 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -i "store\|merchant"''',

    # 3. Test the API directly from gateway
    '''curl -sk -H "Cookie: session=test" https://localhost/api/admin/merchant/stores 2>&1''',

    # 4. Check the admin-web env
    '''sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin env | grep -i "api\|backend\|base"''',
]

for i, cmd in enumerate(checks):
    print(f"\n=== Check {i+1} ===")
    si, so, se = c.exec_command(cmd, timeout=20)
    out = so.read().decode('utf-8', errors='replace').strip()
    err = se.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out[:600])
    if err and 'Warning' not in err:
        print("stderr:", err[:300])

c.close()
