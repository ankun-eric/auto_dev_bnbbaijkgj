import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
print("Connected!", flush=True)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# Backend
out, err = run(f'docker exec {DEPLOY_ID}-backend ls /app/')
print("=== BACKEND /app/ ===")
print(out)
print("ERR:", err[:200] if err else "none")

out, err = run(f'docker exec {DEPLOY_ID}-backend find /app -name "*.py" -path "*api*" 2>/dev/null | head -30')
print("=== BACKEND api py ===")
print(out)

# H5
out, err = run(f'docker exec {DEPLOY_ID}-h5 ls /app/')
print("=== H5 /app/ ===")
print(out)

out, err = run(f'docker exec {DEPLOY_ID}-h5 find /app -name "page.tsx" 2>/dev/null | head -30')
print("=== H5 page.tsx ===")
print(out)

ssh.close()
print("Done!", flush=True)
