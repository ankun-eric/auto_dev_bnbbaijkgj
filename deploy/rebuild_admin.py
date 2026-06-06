import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)
D = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def ssh(cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

print('=== Git Pull ===')
out, err = ssh(f'cd /home/ubuntu/{D} && git fetch codeup master && git reset --hard codeup/master 2>&1')
print(out[-300:] if out else '(empty)')

print('\n=== Rebuild admin ===')
out, err = ssh(f'cd /home/ubuntu/{D} && docker compose -f docker-compose.prod.yml up -d --no-deps --build admin-web 2>&1', timeout=300)
print(out[-500:] if out else '(empty)')

print('\n=== Rebuild h5 ===')
out, err = ssh(f'cd /home/ubuntu/{D} && docker compose -f docker-compose.prod.yml up -d --no-deps --build h5-web 2>&1', timeout=300)
print(out[-500:] if out else '(empty)')

print('\n=== Waiting 30s for health checks... ===')
time.sleep(30)

for svc in ['db', 'backend', 'h5', 'admin']:
    out, err = ssh(f"docker inspect {D}-{svc} --format '{{{{.State.Health.Status}}}}' 2>/dev/null")
    print(f'  {svc}: {out}')

print('\n=== Final Status ===')
out, err = ssh(f'docker ps --filter name={D} --format "table {{{{.Names}}}}\t{{{{.Status}}}}"')
print(out)

client.close()
print('\nDone.')
