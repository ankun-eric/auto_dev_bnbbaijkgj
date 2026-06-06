import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, timeout=15):
    i,o,e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8',errors='replace').strip()
    err = e.read().decode('utf-8',errors='replace').strip()
    return out, err

lines = []

# 1. Disable the duplicate .conf file
lines.append('=== Fix .conf file ===')
o,e = run('cd /home/ubuntu/gateway/conf.d && mv 6b099ed3-7175-4a78-91f4-44570c84ed27.conf 6b099ed3-7175-4a78-91f4-44570c84ed27.conf.dup_disabled 2>&1')
lines.append(f'out: {o}')
lines.append(f'err: {e}')

# 2. Test nginx config
lines.append('\n=== nginx -t ===')
o,e = run('docker exec gateway-nginx nginx -t 2>&1')
lines.append(f'out: {o}')
lines.append(f'err: {e}')

# 3. Reload nginx
lines.append('\n=== nginx reload ===')
o,e = run('docker exec gateway-nginx nginx -s reload 2>&1')
lines.append(f'out: {o}')
lines.append(f'err: {e}')

# 4. Check if gateway is on project network
lines.append('\n=== Network check ===')
o,e = run('docker inspect gateway-nginx --format "{{range .NetworkSettings.Networks}}{{if eq .NetworkID \"168e6fde5a2f991e2bd73e264cd1687253c9d5b841436d231fede1b98e2974f0\"}}CONNECTED{{end}}{{end}}" 2>/dev/null')
lines.append(f'Gateway on project network: {o}')

# 5. DB check
lines.append('\n=== DB check ===')
o,e = run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema=\'bini_health\'" 2>&1')
lines.append(f'DB tables: {o}')
lines.append(f'err: {e}')

# 6. Check users table
lines.append('\n=== Users table ===')
o,e = run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SELECT id, username, is_admin FROM bini_health.users LIMIT 10" 2>&1')
lines.append(f'Users: {o}')
lines.append(f'err: {e}')

# 7. External verify
lines.append('\n=== External verify ===')
o,e = run('curl -sk https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>/dev/null')
lines.append(f'API health: {o}')

o,e = run('curl -sk -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ 2>/dev/null')
lines.append(f'H5 status: {o}')

o,e = run('curl -sk -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/ 2>/dev/null')
lines.append(f'Admin status: {o}')

# 8. Container status
lines.append('\n=== Container status ===')
o,e = run('docker ps --format "{{.Names}} {{.Status}}" 2>/dev/null | grep 6b099ed3')
lines.append(f'Containers: {o}')

result = '\n'.join(lines)
with open('deploy/fix_and_verify_result.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print('DONE')
ssh.close()
