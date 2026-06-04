import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=15)

def run(cmd, t=15):
    si, so, se = c.exec_command(cmd, timeout=t)
    out = so.read().decode('utf-8', errors='replace').strip()
    err = se.read().decode('utf-8', errors='replace').strip()
    return out, err

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DIR = f"/home/ubuntu/{DEPLOY_ID}"

# 1. Check .env
print("=== .env ===")
out, _ = run(f"cat {DIR}/.env")
print(out)

# 2. Check docker-compose DATABASE_URL
print("\n=== docker-compose DATABASE_URL ===")
out, _ = run(f"grep DATABASE_URL {DIR}/docker-compose.prod.yml")
print(out)

# 3. Check actual container env
print("\n=== 容器内 DATABASE_URL ===")
out, _ = run(f"sudo docker exec {DEPLOY_ID}-backend bash -c 'echo \$DATABASE_URL'")
print(out)

# 4. Check if there's a .env.production
print("\n=== .env.production ===")
out, _ = run(f"cat {DIR}/.env.production 2>/dev/null || echo NOT_FOUND")
print(out)

c.close()
