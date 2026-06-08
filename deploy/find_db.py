#!/usr/bin/env python3
"""Find the correct MySQL database container"""
import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=20):
    print(f'\n[CMD] {cmd[:200]}')
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(f'[OUT] {out.strip()[:800]}')
    if err.strip(): print(f'[ERR] {err.strip()[:400]}')
    sys.stdout.flush()

# Find all running containers with mysql in name
print("=" * 60)
print("MySQL containers running")
print("=" * 60)
run("docker ps --filter name=mysql --format '{{.Names}} {{.Image}} {{.Ports}}'")
run("docker ps --filter name=db --format '{{.Names}} {{.Image}} {{.Ports}}'")

# Check noob_ai-db specifically
print("\n" + "=" * 60)
print("Check noob_ai-db")
print("=" * 60)
run("docker inspect noob_ai-db --format '{{.NetworkSettings.Networks}}' 2>&1 | head -20")
run("docker port noob_ai-db 2>&1")

# Check 622c312c-...-mysql
print("\n" + "=" * 60)
print("Check 622c312c-mysql")
print("=" * 60)
run("docker network inspect 622c312c-ea3e-4c32-af33-9836db929371-network --format '{{range .Containers}}{{.Name}} {{end}}'")

# Try connecting to noob_ai-db from project network
print("\n" + "=" * 60)
print("Connect noob_ai-db to project network")
print("=" * 60)
run("docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network noob_ai-db 2>&1 || echo 'already'")

# Check if bini_health database exists
print("\n" + "=" * 60)
print("Check bini_health database")
print("=" * 60)
run("docker exec noob_ai-db mysql -u root -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -20")

# Now update docker-compose to use noob_ai-db as host
print("\n" + "=" * 60)
print("Fix DATABASE_URL to use noob_ai-db")
print("=" * 60)
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/deploy && sed -i 's|@db:3306|@noob_ai-db:3306|g' docker-compose.prod.yml && grep DATABASE_URL docker-compose.prod.yml")

# Also update .env
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/deploy && sed -i 's|@db:3306|@noob_ai-db:3306|g' .env 2>/dev/null; cat .env | grep DATABASE_URL")

# Restart backend
print("\n" + "=" * 60)
print("Restart backend")
print("=" * 60)
run("docker restart 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1")

ssh.close()
print("\nDone!")
