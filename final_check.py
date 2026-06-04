import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
def run(cmd, timeout=10):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

with open('C:/auto_output/bnbbaijkgj/final_summary.txt', 'w') as f:
    f.write("=== Admin Account ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e \"SELECT id, phone, role, is_superuser, status FROM users WHERE role='admin' LIMIT 5;\" 2>&1")
    f.write(out + "\n")

    f.write("=== Admin Login Test ===\n")
    out, err = run("curl -sk -X POST https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -H 'Content-Type: application/json' -d '{\"phone\":\"13800000000\",\"password\":\"admin123\"}' 2>&1")
    f.write(f"Login: {out[:300]}\n")

    f.write("\n=== Container Health ===\n")
    out, err = run("docker ps --filter name=6b099ed3 --format '{{.Names}}: {{.Status}}'")
    f.write(out + "\n")

    f.write("\n=== Cleanup temp files ===\n")
    out, err = run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && ls *.py 2>&1 | wc -l")
    f.write(f"Python files in project dir: {out}\n")

ssh.close()
print("DONE")
