import paramiko, sys
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('chat.benne-ai.com', port=22, username='ubuntu', password='Benne-ai@#', timeout=15)

def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=30, get_pty=True)
    return o.read().decode() + e.read().decode()

print("=== DOCKER PS ===")
print(run('docker ps -a --filter name=6b099ed3 --format "{{.Names}} {{.Status}}"'))
print("=== DOCKER COMPOSE ===")
print(run('docker compose version 2>&1'))
print("=== CONF PERM ===")
print(run('ls -la /home/ubuntu/gateway/conf.d/6b099ed3* 2>&1'))
print("=== IMAGES ===")
print(run('docker images --filter reference=*6b099ed3* --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}"'))
print("=== NETWORK ===")
print(run('docker network inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-network --format "{{range .Containers}}{{.Name}} {{end}}"'))
ssh.close()
print("DONE")
