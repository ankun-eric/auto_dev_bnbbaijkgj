import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

with open('C:/auto_output/bnbbaijkgj/health_check_result.txt', 'w') as f:
    f.write("=== Check wget in h5 container ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 which wget 2>&1")
    f.write(f"wget: {out} {err}\n")
    
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin which wget 2>&1")
    f.write(f"admin wget: {out} {err}\n")
    
    f.write("\n=== Try healthcheck command directly ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 wget -qO- http://localhost:3001/ 2>&1")
    f.write(f"h5 wget test: {out[:200]} {err[:200]}\n")
    
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin wget -qO- http://localhost:3000/admin 2>&1")
    f.write(f"admin wget test: {out[:200]} {err[:200]}\n")
    
    f.write("\n=== Container inspect health ===\n")
    out, err = run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 --format '{{json .State.Health}}' 2>&1")
    f.write(f"h5 health: {out[:500]}\n")
    
    out, err = run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-admin --format '{{json .State.Health}}' 2>&1")
    f.write(f"admin health: {out[:500]}\n")

ssh.close()
print("DONE")
