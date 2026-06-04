import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=15)

def run(cmd, t=20):
    si, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode('utf-8', errors='replace').strip()

# Check 1: Find store-related code
print("=== 后端门店API代码 ===")
out = run("sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend find /app -name '*.py' -path '*store*' 2>/dev/null | head -10", t=15)
print(out)

out = run("sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend find /app -name '*.py' -path '*merchant*' 2>/dev/null | head -15", t=15)
print(out)

# Check 2: Look at the store router
print("\n=== 门店路由代码 ===")
out = run("sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend cat /app/app/api/admin/merchant.py 2>/dev/null | head -80 || echo NOT_FOUND", t=15)
print(out[:1500])

# Check 3: Check the database connection inside container
print("\n=== 容器内数据库连接测试 ===")
out = run("sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c \"import os; print('DATABASE_URL:', os.environ.get('DATABASE_URL','NOT SET')[:80])\" 2>&1", t=15)
print(out)

c.close()
