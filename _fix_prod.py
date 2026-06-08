#!/usr/bin/env python3
import paramiko, time, sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=20, allow_agent=False, look_for_keys=False)

def run(cmd, t=30):
    print(f"  $ {cmd[:120]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(f"    out: {out.strip()[:400]}")
    if err.strip(): print(f"    err: {err.strip()[:300]}")
    return out + err

# Step 1: Stop and remove the db container
print("=== Step 1: Clean up ===")
run("docker stop 6b099ed3-7175-4a78-91f4-44570c84ed27-db 2>&1 || echo 'no db'")
run("docker rm 6b099ed3-7175-4a78-91f4-44570c84ed27-db 2>&1 || echo 'no db rm'")

# Step 2: Remove old containers properly
print("\n=== Step 2: Down old containers ===")
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml down 2>&1 || echo 'down done'")

# Step 3: Upload fixed docker-compose (without db dep)
print("\n=== Step 3: Fix docker-compose ===")
# Remove db service and its dependencies
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && sed -i '/depends_on:/,/condition: service_healthy/{/depends_on:/d; /db:/d; /condition:/d}' docker-compose.prod.yml 2>&1 || echo 'sed done'")

# Step 4: Build and start
print("\n=== Step 4: Build and start ===")
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web admin-web 2>&1", 600)
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d backend h5-web admin-web 2>&1")

# Step 5: Wait
print("\n=== Step 5: Wait for startup ===")
time.sleep(30)

# Step 6: Check
print("\n=== Step 6: Verify ===")
run("docker ps --format 'table {{.Names}}\t{{.Status}}' --filter name=6b099ed 2>&1")
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend printenv DATABASE_URL 2>&1")
run("curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/api/health 2>&1")
run("curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/ 2>&1")
run("curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/admin/ 2>&1")

# Step 7: Gateway network
run("docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway-nginx 2>&1 || echo 'already connected'")
run("docker exec gateway-nginx nginx -t 2>&1")
run("docker exec gateway-nginx nginx -s reload 2>&1")

print("\nDONE")
c.close()
