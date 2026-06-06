import paramiko, time, json, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run_cmd(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode()+'\n'+stderr.read().decode()

log = []

# 1. Git pull
log.append("=== Git pull ===")
result = run_cmd('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git fetch origin master && git reset --hard origin/master && git log -1 --oneline', 60)
log.append(result[:500])

# 2. Rebuild all
for svc in ['backend', 'admin', 'h5']:
    log.append(f"=== Rebuild {svc} ===")
    result = run_cmd(f'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml build {svc} 2>&1 | tail -30', 300)
    log.append(result[:500])

# 3. Restart
log.append("=== docker compose up -d ===")
result = run_cmd('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d 2>&1', 120)
log.append(result[:500])

# 4. Wait for healthy
log.append("=== Wait for healthy ===")
time.sleep(30)
result = run_cmd('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml ps --format json', 30)
containers = []
for line in result.split('\n'):
    if line.strip() and '{' in line:
        try:
            c = json.loads(line)
            containers.append({'name': c.get('Name','?'), 'state': c.get('State','?'), 'health': c.get('Health','?')})
        except: pass
status_str = '\n'.join([f"  {c['name']}: {c['state']} (Health: {c['health']})" for c in containers])
log.append(status_str)

# 5. Verify
log.append("=== Verify server-time ===")
result = run_cmd('curl -s --connect-timeout 5 http://localhost:8000/api/system/server-time', 15)
log.append(result[:200])

log.append("=== Verify health ===")
result = run_cmd('curl -s --connect-timeout 5 http://localhost:8000/api/health', 15)
log.append(result[:200])

ssh.close()

log_text = '\n'.join(log)
with open(r'C:\auto_output\bnbbaijkgj\_redeploy_result.txt', 'w') as f:
    f.write(log_text)

print('Redeploy complete. Writing to _redeploy_result.txt')
