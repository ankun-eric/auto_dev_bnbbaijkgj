import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

with open('C:/auto_output/bnbbaijkgj/db_check_result.txt', 'w') as f:
    f.write("=== Users table columns ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e 'DESCRIBE users;' 2>&1")
    f.write(out + "\n" + err + "\n\n")
    
    f.write("=== Admin users (phone like admin) ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e \"SELECT id, phone, role FROM users WHERE phone LIKE '%admin%' OR id=1 LIMIT 5;\" 2>&1")
    f.write(out + "\n" + err + "\n\n")

    f.write("=== All users count ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e 'SELECT COUNT(*) as total_users FROM users;' 2>&1")
    f.write(out + "\n" + err + "\n\n")

    f.write("=== Container health status ===\n")
    out, err = run("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'")
    f.write(out + "\n\n")

ssh.close()
print("DONE")
