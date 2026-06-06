import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    i,o,e = ssh.exec_command(cmd, timeout=15)
    return o.read().decode('utf-8',errors='replace').strip()

lines = []

# Check users table structure
lines.append('=== Users table columns ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SHOW COLUMNS FROM bini_health.users" 2>&1'))

lines.append('\n=== First 5 users ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SELECT * FROM bini_health.users LIMIT 5" 2>&1'))

lines.append('\n=== Check accounts table ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SHOW TABLES FROM bini_health LIKE \"%account%\" OR LIKE \"%admin%\" OR LIKE \"%user%\"" 2>&1'))

lines.append('\n=== All tables matching auth/user ===')
lines.append(run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -e "SHOW TABLES FROM bini_health" 2>&1 | grep -iE "user|account|admin|auth|login"'))

result = '\n'.join(lines)
with open('deploy/db_users_result.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print('DONE')
ssh.close()
