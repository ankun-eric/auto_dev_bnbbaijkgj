import paramiko, time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
               look_for_keys=False, allow_agent=False)

def run(cmd, timeout=30):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    out = b""
    deadline = time.time() + timeout
    while not chan.exit_status_ready():
        if time.time() > deadline:
            break
        if chan.recv_ready():
            out += chan.recv(65536)
        time.sleep(0.1)
    try:
        out += chan.recv(65536)
    except:
        pass
    return out.decode(errors='replace'), chan.exit_status

print("=" * 70)
print("FINAL VERIFICATION REPORT")
print("=" * 70)

# 1. Container status
print("\n[1] Container Status:")
out, _ = run(f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Image}}}}'")
print(out)

# 2. Nginx status
print("[2] Nginx Status:")
out, _ = run(f"docker exec gateway-nginx sh -c 'nginx -T 2>&1 | grep -c \"{DEPLOY_ID}\"'")
print(f"  References to {DEPLOY_ID} in nginx config: {out.strip()}")

# 3. Migration log
print("\n[3] Migration Log:")
out, _ = run(f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from app.core.database import async_session; from sqlalchemy import text; async def q(): async with async_session() as db: r = await db.execute(text('SELECT table_name, column_name, affected_rows FROM _migration_bucket_log ORDER BY affected_rows DESC LIMIT 10')); [print(f'  {row[0]}.{row[1]}: {row[2]} rows') for row in r.fetchall()]; asyncio.run(q())\" 2>&1")
print(out[:500])

# 4. Default admin account check
print("\n[4] Default Admin Account Check:")
out, _ = run(f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from app.core.database import async_session; from sqlalchemy import text; async def q(): async with async_session() as db: r = await db.execute(text(\\\"SELECT username FROM users WHERE username='admin' LIMIT 1\\\")); rows = r.fetchall(); print('Admin exists' if rows else 'Admin NOT found'); asyncio.run(q())\" 2>&1")
print(f"  {out.strip()}")

# 5. External access test
print("\n[5] External HTTPS Access Test:")
out, _ = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/api/health 2>&1")
print(f"  /api/health: HTTP {out.strip()}")
out, _ = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/ 2>&1")
print(f"  / (H5): HTTP {out.strip()}")
out, _ = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/admin/ 2>&1")
print(f"  /admin/: HTTP {out.strip()}")

# 6. SSL Certificate
print("\n[6] SSL Certificate:")
out, _ = run(f"curl -vIk https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/ 2>&1 | grep -iE 'subject:|issuer:|expire|SSL connection' | head -5")
print(f"  {out.strip()[:300]}")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)

client.close()
