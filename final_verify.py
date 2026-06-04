import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, timeout=10):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

with open('C:/auto_output/bnbbaijkgj/final_result.txt', 'w') as f:
    # Wait for all containers to be fully healthy
    f.write("=== Waiting for full health ===\n")
    for i in range(12):
        time.sleep(5)
        out, err = run("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'")
        f.write(f"[{i+1}] {out}\n")
        if out and all('(healthy)' in l for l in out.split('\n')):
            f.write("ALL HEALTHY!\n")
            break
    
    f.write("\n=== Final Container Status ===\n")
    out, err = run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
    f.write(out + "\n\n")
    
    f.write("=== HTTPS Endpoints ===\n")
    for path in ['/api/health', '/api/docs', '/', '/admin/']:
        out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}{path} 2>&1")
        f.write(f"https://{DOMAIN}{path} -> HTTP {out}\n")
    
    f.write("\n=== Admin Login Test ===\n")
    out, err = run(f"curl -sk -X POST https://{DOMAIN}/api/auth/login -H 'Content-Type: application/json' -d '{{\"phone\":\"13800000000\",\"password\":\"admin123\"}}' 2>&1", timeout=10)
    f.write(f"Login response: {out[:300]}\n")
    
    f.write("\n=== Database Check ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e 'SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema=\"bini_health\";' 2>&1")
    f.write(f"Tables count: {out}\n")
    
    f.write("\n=== Healthcheck Config Verification ===\n")
    out, err = run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format '{{.Config.Healthcheck}}' 2>&1")
    f.write(f"Backend healthcheck: {out[:200]}\n")
    
    out, err = run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 --format '{{.Config.Healthcheck}}' 2>&1")
    f.write(f"H5 healthcheck: {out[:200]}\n")
    
    out, err = run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-admin --format '{{.Config.Healthcheck}}' 2>&1")
    f.write(f"Admin healthcheck: {out[:200]}\n")

ssh.close()
print("DONE")
