import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)
D = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def ssh(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

print('=== External API Test ===')
out, err = ssh(f'curl -sk https://{D}.noob-ai.test.bangbangvip.com/api/health 2>&1')
print(f'  {out}')

print('\n=== External H5 Test ===')
out, err = ssh(f'curl -sk -o /dev/null -w "HTTP:%{{http_code}} Size:%{{size_download}}" https://{D}.noob-ai.test.bangbangvip.com/ 2>&1')
print(f'  {out}')

print('\n=== External Admin Test ===')
out, err = ssh(f'curl -sk -o /dev/null -w "HTTP:%{{http_code}} Size:%{{size_download}}" https://{D}.noob-ai.test.bangbangvip.com/admin/ 2>&1')
print(f'  {out}')

print('\n=== External API Login Test (admin/admin123) ===')
out, err = ssh(f"curl -sk -X POST https://{D}.noob-ai.test.bangbangvip.com/api/auth/login -H 'Content-Type: application/json' -d '{{\"phone\":\"admin\",\"password\":\"admin123\"}}' 2>&1")
print(f'  {out[:300]}')

print('\n=== DB Admin Accounts ===')
out, err = ssh(f"docker exec {D}-db mysql -uroot -pbini_health_2026 bini_health -e \"SELECT id,phone,nickname,role,is_active FROM users WHERE phone='admin' OR phone='13800000000'\" 2>&1")
print(f'  {out}')

print('\n=== All Containers ===')
out, err = ssh(f'docker ps --filter name={D} --format "table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"')
print(out)

print('\n=== Disk ===')
out, err = ssh('df -h / | tail -1')
print(f'  {out}')

client.close()
print('\nDone.')
