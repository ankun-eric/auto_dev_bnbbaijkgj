import paramiko, json, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

results = {}

# Check git
stdin, stdout, stderr = ssh.exec_command('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git log -1 --oneline')
results['git_head'] = stdout.read().decode().strip()

# Check containers
stdin, stdout, stderr = ssh.exec_command('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml ps --format json')
raw = stdout.read().decode().strip()
containers = []
for line in raw.split('\n'):
    if line.strip():
        try:
            c = json.loads(line)
            containers.append({'name': c.get('Name','?'), 'state': c.get('State','?'), 'health': c.get('Health','?')})
        except:
            pass
results['containers'] = containers

# Check server time
stdin, stdout, stderr = ssh.exec_command('curl -s --connect-timeout 5 http://localhost:8000/api/system/server-time')
results['server_time'] = stdout.read().decode().strip()

# Check health
stdin, stdout, stderr = ssh.exec_command('curl -s --connect-timeout 5 http://localhost:8000/api/health')
results['health'] = stdout.read().decode().strip()

ssh.close()

# Write to file
with open(r'C:\auto_output\bnbbaijkgj\_deploy_check_result.txt', 'w') as f:
    f.write(f"Git HEAD: {results['git_head']}\n\n")
    f.write("Containers:\n")
    for c in results['containers']:
        f.write(f"  {c['name']}: {c['state']} (Health: {c['health']})\n")
    f.write(f"\nServer time: {results['server_time']}\n")
    f.write(f"Health: {results['health']}\n")

print('Done. Results written to _deploy_check_result.txt')
