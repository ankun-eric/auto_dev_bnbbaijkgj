import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    i,o,e = ssh.exec_command(cmd, timeout=15)
    return o.read().decode('utf-8',errors='replace').strip()

lines = []

# Check account_identities
lines.append('=== account_identities table ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SHOW COLUMNS FROM bini_health.account_identities" 2>&1'))

lines.append('\n=== account_identities data ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SELECT * FROM bini_health.account_identities LIMIT 5" 2>&1'))

# Check admin users specifically
lines.append('\n=== Admin users ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SELECT id, phone, role, is_superuser, status FROM bini_health.users WHERE role=\'admin\' OR is_superuser=1" 2>&1'))

# Gateway network verify
lines.append('\n=== Gateway in project network ===')
lines.append(run('docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-network --format "{{range .Containers}}{{.Name}}\n{{end}}" 2>/dev/null'))

# Final external check
lines.append('\n=== Final external verification ===')
lines.append(run('curl -sk https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>/dev/null'))
lines.append(run('curl -sk -o /dev/null -w "H5: %{http_code}\n" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ 2>/dev/null'))
lines.append(run('curl -sk -o /dev/null -w "Admin: %{http_code}\n" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/ 2>/dev/null'))

result = '\n'.join(lines)
with open('deploy/final_check_result.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print('DONE')
ssh.close()
