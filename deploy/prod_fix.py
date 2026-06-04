import paramiko, time, os

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=15)

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL = r"C:\auto_output\bnbbaijkgj\deploy\docker-compose.prod.yml"
REMOTE = f"/home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml"

def run(cmd, t=60):
    si, so, se = c.exec_command(cmd, timeout=t)
    out = so.read().decode('utf-8', errors='replace').strip()
    err = se.read().decode('utf-8', errors='replace').strip()
    code = so.channel.recv_exit_status()
    if out:
        print(out[:500])
    if err and 'Warning' not in err and err.strip():
        print("ERR:", err[:300])
    return out, err, code

# Step 1: Upload
print("=== 1. Upload ===")
sftp = c.open_sftp()
sftp.put(LOCAL, REMOTE)
sftp.close()
print("OK")

# Step 2: Verify
print("\n=== 2. Verify DATABASE_URL ===")
run(f"grep DATABASE_URL {REMOTE}")

# Step 3: Recreate
print("\n=== 3. Recreate containers ===")
run(f"cd /home/ubuntu/{DEPLOY_ID} && sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true")
run(f"cd /home/ubuntu/{DEPLOY_ID} && sudo docker compose -f docker-compose.prod.yml up -d 2>&1")

# Step 4: Wait health
print("\n=== 4. Wait health ===")
for i in range(24):
    time.sleep(5)
    si, so, se = c.exec_command(
        f"sudo docker compose -f {REMOTE} ps --format json 2>/dev/null", timeout=10)
    out = so.read().decode('utf-8', errors='replace').strip()
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    print(f"  [{i+1}/24] {healthy}/{total} healthy")
    if total >= 3 and healthy >= total:
        print("  All healthy!")
        break

# Step 5: Gateway
print("\n=== 5. Gateway ===")
run("sudo docker rm -f gateway-nginx 2>/dev/null || true")
run(
    "sudo docker run -d --name gateway-nginx --restart unless-stopped "
    "-p 80:80 -p 443:443 "
    "-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
    "-v /home/ubuntu/gateway/conf.d/:/etc/nginx/conf.d/:ro "
    "-v /home/ubuntu/gateway/ssl/:/etc/nginx/ssl/:ro "
    "nginx:alpine 2>&1"
)
run(f"sudo docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true")
run("sudo docker exec gateway-nginx nginx -s reload 2>&1")

# Step 6: Test
print("\n=== 6. Test ===")
time.sleep(3)
run("curl -sk https://localhost/api/health 2>&1")
run("curl -sI -k https://chat.benne-ai.com/ 2>&1 | head -3")

print("\nDone!")
c.close()
