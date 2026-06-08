import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('chat.benne-ai.com', port=22, username='ubuntu', password='Benne-ai@#', timeout=30)

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30, get_pty=True)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out + err

print("=== GATEWAY NGINX.CONF ===")
result = run("cat /home/ubuntu/gateway/nginx.conf")
print(result[:6000])

print("\n=== CONFD DIR ===")
result = run("ls -la /home/ubuntu/gateway/conf.d/")
print(result[:3000])

print("\n=== SSL DIR ===")
result = run("ls -la /home/ubuntu/gateway/ssl/")
print(result[:1000])

print("\n=== PROJECT DIR ===")
result = run("ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/")
print(result[:3000])

print("\n=== DOCKER PS ===")
result = run("docker ps --format 'table {{.Names}}\t{{.Status}}'")
print(result[:3000])

print("\n=== NETWORK CHECK ===")
result = run("docker network inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-network 2>&1 | head -30")
print(result[:2000])

ssh.close()
print("\nDONE")
