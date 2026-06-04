import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

with open('C:/auto_output/bnbbaijkgj/fix_health_result.txt', 'w') as f:
    f.write("=== Check listening ports in h5 ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 netstat -tlnp 2>&1 || docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ss -tlnp 2>&1")
    f.write(f"h5 ports: {out[:500]} {err[:200]}\n")
    
    f.write("\n=== Check listening ports in admin ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin netstat -tlnp 2>&1 || docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin ss -tlnp 2>&1")
    f.write(f"admin ports: {out[:500]} {err[:200]}\n")
    
    f.write("\n=== Try curl from inside h5 ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'wget -qO- http://0.0.0.0:3001/ 2>&1 || wget -qO- http://127.0.0.1:3001/ 2>&1'")
    f.write(f"h5 wget 0.0.0.0: {out[:200]} {err[:200]}\n")
    
    f.write("\n=== Try from admin ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin sh -c 'wget -qO- http://0.0.0.0:3000/admin 2>&1 || wget -qO- http://127.0.0.1:3000/admin 2>&1'")
    f.write(f"admin wget 0.0.0.0: {out[:200]} {err[:200]}\n")
    
    f.write("\n=== Check node process in h5 ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ps aux 2>&1")
    f.write(f"h5 ps: {out[:500]}\n")
    
    f.write("\n=== Check node process in admin ===\n")
    out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin ps aux 2>&1")
    f.write(f"admin ps: {out[:500]}\n")
    
    f.write("\n=== Try from gateway (docker network) ===\n")
    out, err = run("docker exec gateway-nginx wget -qO- http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3001/ 2>&1")
    f.write(f"gw -> h5: {out[:200]} {err[:200]}\n")
    
    out, err = run("docker exec gateway-nginx wget -qO- http://6b099ed3-7175-4a78-91f4-44570c84ed27-admin:3000/admin 2>&1")
    f.write(f"gw -> admin: {out[:200]} {err[:200]}\n")

ssh.close()
print("DONE")
