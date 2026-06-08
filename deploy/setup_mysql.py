#!/usr/bin/env python3
"""Add MySQL service to docker-compose and restart everything"""
import paramiko, sys, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=30):
    print('\n[CMD] ' + cmd[:200])
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print('[OUT] ' + out.strip()[:900])
    if err.strip(): print('[ERR] ' + err.strip()[:400])
    sys.stdout.flush()
    return out, err

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# Step 1: First try to find if there is MySQL on the host itself
print("=" * 60)
print("Step 1: Check host MySQL")
print("=" * 60)
run("which mysql 2>&1")
run("systemctl status mysql 2>&1 | head -5")
run("ps aux | grep mysql | grep -v grep | head -5")

# Step 2: Check if we can use 622c312c-mysql by finding its password
print("\n" + "=" * 60)
print("Step 2: Find 622c312c-mysql password")
print("=" * 60)
run("docker inspect 622c312c-ea3e-4c32-af33-9836db929371-mysql --format '{{json .Config.Env}}' 2>&1")

# Step 3: Check other MySQL containers
print("\n" + "=" * 60)
print("Step 3: Try other MySQL containers")
print("=" * 60)
# Check 538865dd-mysql
run("docker exec 538865dd-add6-44d3-ad7f-d1ff839f1e04-mysql mysql -u root -proot -e 'SELECT 1;' 2>&1 | head -5")
run("docker exec 538865dd-add6-44d3-ad7f-d1ff839f1e04-mysql mysql -u root -e 'SELECT 1;' 2>&1 | head -5")

# Step 4: Since we can't easily find MySQL password, add MySQL to docker-compose
print("\n" + "=" * 60)
print("Step 4: Add MySQL to docker-compose.prod.yml")
print("=" * 60)

# Read current docker-compose
stdin, stdout, stderr = ssh.exec_command(f"cat /home/ubuntu/{DEPLOY_ID}/deploy/docker-compose.prod.yml")
current_compose = stdout.read().decode('utf-8', errors='replace')

# Add db service before 'volumes:' section
db_service = """
  db:
    image: crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/mysql:8.0
    container_name: {DEPLOY_ID}-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: bini_health_2026
      MYSQL_DATABASE: bini_health
      MYSQL_CHARSET: utf8mb4
      MYSQL_COLLATION: utf8mb4_unicode_ci
    ports:
      - "127.0.0.1:3307:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      app-network:
        aliases:
          - {DEPLOY_ID}-db

""".format(DEPLOY_ID=DEPLOY_ID)

# Check if db service already exists
if 'container_name: {DEPLOY_ID}-db'.format(DEPLOY_ID=DEPLOY_ID) not in current_compose:
    # Insert db service before volumes
    new_compose = current_compose.replace('\nvolumes:', db_service + '\nvolumes:')
    # Add mysql_data volume
    new_compose = new_compose.replace('volumes:\n  uploads_data:', 'volumes:\n  mysql_data:\n  uploads_data:')
    
    # Write updated compose
    sftp = ssh.open_sftp()
    with sftp.file(f'/home/ubuntu/{DEPLOY_ID}/deploy/docker-compose.prod.yml', 'w') as f:
        f.write(new_compose)
    sftp.close()
    print("Added MySQL service to docker-compose.prod.yml")
else:
    print("MySQL service already exists in compose")

# Update DATABASE_URL to use local db
run(f"cd /home/ubuntu/{DEPLOY_ID}/deploy && sed -i 's|DATABASE_URL:.*|DATABASE_URL: mysql+aiomysql://root:bini_health_2026@{DEPLOY_ID}-db:3306/bini_health|g' docker-compose.prod.yml")
run(f"grep DATABASE_URL /home/ubuntu/{DEPLOY_ID}/deploy/docker-compose.prod.yml")

# Step 5: Restart everything
print("\n" + "=" * 60)
print("Step 5: Redeploy with MySQL")
print("=" * 60)
run(f"cd /home/ubuntu/{DEPLOY_ID}/deploy && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1")
time.sleep(3)
run(f"cd /home/ubuntu/{DEPLOY_ID}/deploy && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=180)

time.sleep(30)

# Step 6: Check status
print("\n" + "=" * 60)
print("Step 6: Status check")
print("=" * 60)
run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")

# Backend logs
run(f"docker logs {DEPLOY_ID}-backend --tail 20 2>&1")

# HTTP check
print("\n--- HTTP check ---")
domain = f'{DEPLOY_ID}.noob-ai.test.bangbangvip.com'
run(f"curl -sk -w 'HTTP:%{{http_code}}' https://{domain}/api/health 2>&1 | tail -3")

ssh.close()
print("\nDone!")
