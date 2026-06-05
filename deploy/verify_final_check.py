"""Final account and API verification."""
import paramiko, json, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)
print('Connected', flush=True)

def run(cmd, timeout=15):
    print(f'\n>>> {cmd[:100]}', flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f'EXIT={ec}', flush=True)
    if out.strip(): print(out[:600], flush=True)
    if err.strip() and ec != 0: print('ERR:', err[:300], flush=True)
    return ec, out, err

DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DID}.noob-ai.test.bangbangvip.com"

# Health check
run(f"curl -sk https://{DOMAIN}/api/health")

# Try login with admin/admin123
login_data = '{"username":"admin","password":"admin123"}'
run(f"curl -sk -X POST https://{DOMAIN}/api/auth/login -H 'Content-Type: application/json' -d '{login_data}'")

# Try admin login with different endpoint
run(f"curl -sk -X POST https://{DOMAIN}/api/login -H 'Content-Type: application/json' -d '{login_data}'")

# List available auth endpoints
run(f"curl -sk https://{DOMAIN}/api/docs 2>&1 | head -3")

# Check from inside backend container
run(f"docker exec {DID}-backend python3 -c \"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read().decode())\"")

ssh.close()
print('\nDone', flush=True)
