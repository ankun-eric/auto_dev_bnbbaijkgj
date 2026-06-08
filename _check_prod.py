#!/usr/bin/env python3
import paramiko, sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=20, allow_agent=False, look_for_keys=False)

def run(cmd, t=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out.strip(), err.strip()

out, _ = run('docker ps -a --format "table {{.Names}}\t{{.Status}}"')
print("=== DOCKER ===")
print(out)

out, _ = run('ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ | head -30')
print("\n=== PROJECT DIR ===")
print(out)

out, _ = run('ls /home/ubuntu/gateway/conf.d/')
print("\n=== GATEWAY CONF ===")
print(out)

out, _ = run('head -25 /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.prod.yml')
print("\n=== DOCKER-COMPOSE.PROD.YML (head) ===")
print(out)

out, _ = run('cat /home/ubuntu/gateway/conf.d/*.conf 2>/dev/null | head -80')
print("\n=== GATEWAY CONFIG ===")
print(out)

out, _ = run('df -h / | tail -1')
print("\n=== DISK ===")
print(out)

c.close()
