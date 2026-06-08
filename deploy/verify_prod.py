import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=20, allow_agent=False, look_for_keys=False)

# Verify health with GET
print("=== /api/health GET ===")
stdin, stdout, stderr = c.exec_command('curl -s https://chat.benne-ai.com/api/health')
out = stdout.read().decode()
err = stderr.read().decode()
print("out:", out.strip())
if err: print("err:", err.strip())

# Check DB via backend container
print("\n=== DB Check ===")
sql = 'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c "from app.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); tables = inspector.get_table_names(); print(len(tables), sorted(tables)[:15])" 2>&1'
stdin, stdout, stderr = c.exec_command(sql, timeout=30)
out = stdout.read().decode()
err = stderr.read().decode()
print("tables:", out.strip())
if err: print("err:", err[:500])

# Check admin account
print("\n=== Admin Account ===")
sql2 = 'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c "from app.database import engine; from sqlalchemy import text; with engine.connect() as conn: r = conn.execute(text(\"SELECT username, role FROM users WHERE username=\\\"admin\\\" LIMIT 1\")); print([dict(row) for row in r.fetchall()])" 2>&1'
stdin, stdout, stderr = c.exec_command(sql2, timeout=30)
out = stdout.read().decode()
err = stderr.read().decode()
print("admin:", out.strip())
if err: print("err:", err[:300])

# SSL check
print("\n=== SSL ===")
stdin, stdout, stderr = c.exec_command('curl -vI https://chat.benne-ai.com/ 2>&1 | grep -iE "SSL|subject|issuer|expire|200|301"')
out = stdout.read().decode()
print(out.strip())

c.close()
