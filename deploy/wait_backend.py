#!/usr/bin/env python3
"""Wait for backend to fully initialize and verify deployment"""
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

domain = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

# Check backend progress every 15 seconds
for i in range(8):
    print(f'\n{"="*40}')
    print(f'Check {i+1}/8 (elapsed: {i*15}s)')
    print(f'{"="*40}')
    
    run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
    
    # Check backend logs for errors
    out, _ = run("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail 10 2>&1")
    
    # Try HTTP
    out, _ = run(f"curl -sk -w 'HTTP:%{{http_code}}' https://{domain}/api/health 2>&1")
    
    if 'HTTP:200' in out:
        print('\n*** BACKEND IS UP! ***')
        break
    
    if i < 7:
        time.sleep(15)

# Final comprehensive check
print("\n" + "=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)

print("\n--- Container Status ---")
run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")

print("\n--- Backend Logs (last 30) ---")
run("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail 30 2>&1")

print("\n--- DB Logs ---")
run("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-db --tail 10 2>&1")

print("\n--- HTTP Endpoints ---")
run(f"curl -sk -w '\\nHTTP:%{{http_code}}\\n' https://{domain}/api/health")
run(f"curl -sk -w '\\nHTTP:%{{http_code}}\\n' https://{domain}/")
run(f"curl -sk -w '\\nHTTP:%{{http_code}}\\n' https://{domain}/admin/")

# Verify DB by checking tables
print("\n--- Database Tables ---")
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -u root -pbini_health_2026 -e 'SHOW TABLES FROM bini_health;' 2>&1 | head -40")

ssh.close()
print("\nDone!")
