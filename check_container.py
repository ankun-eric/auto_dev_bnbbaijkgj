#!/usr/bin/env python3
import paramiko

HOST = "newbb.test.bangbangvip.com"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
CONTAINER_NAME = f"{DEPLOY_ID}-admin"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username="ubuntu", password="Bangbang987", timeout=30)

def run(cmd, timeout=60):
    print(f">>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err:
        print("STDERR:", err[:500])
    return out, err

# Check where next binary is
run(f'docker exec {CONTAINER_NAME} sh -c "ls /app/node_modules/.bin/ | grep next"')
run(f'docker exec {CONTAINER_NAME} sh -c "ls /app/node_modules/.bin/ | head -30"')
run(f'docker exec {CONTAINER_NAME} sh -c "cat /app/package.json"')

client.close()
