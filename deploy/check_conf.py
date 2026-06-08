import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('chat.benne-ai.com', port=22, username='ubuntu', password='Benne-ai@#', timeout=30)

def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=30, get_pty=True)
    return o.read().decode() + e.read().decode()

print("=== SERVER CONF ===")
print(run("cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf"))
print("\n=== BACKEND APP DIR ===")
print(run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/app/ 2>&1 | head -20"))
print("\n=== BACKEND PYTHON PATH ===")
print(run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -c 'import sys; print(sys.path[:5])' 2>&1"))
print("\n=== BACKEND BUILD INFO ===")
print(run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend cat /app/BUILD_INFO 2>&1"))
ssh.close()
