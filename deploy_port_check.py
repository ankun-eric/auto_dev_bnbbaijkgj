import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS)

def run_cmd(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

# Check what's listening on port 8000
out, _ = run_cmd("sudo ss -tlnp | grep 8000")
print(f"Port 8000 listeners:\n{out}")

# Check iptables DNAT rules for 8000
out, _ = run_cmd("sudo iptables -t nat -L DOCKER -n --line-numbers | grep 8000")
print(f"\nIPTABLES DOCKER NAT for 8000:\n{out}")

# Check docker port mappings  
out, _ = run_cmd("docker ps --format '{{.Names}}\t{{.Ports}}' | grep 8000")
print(f"\nDocker port 8000 mappings:\n{out}")

# Test directly from server to localhost:8000
out, _ = run_cmd('curl -s http://localhost:8000/api/health')
print(f"\nlocalhost:8000 health: {out}")

# Test from the external IP
out, _ = run_cmd('curl -s http://10.0.8.15:8000/api/health')
print(f"\n10.0.8.15:8000 health: {out}")

ssh.close()
