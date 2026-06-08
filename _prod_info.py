#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=20, allow_agent=False, look_for_keys=False)

def run(cmd, t=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return (out + err).strip()

print("=== GIT HEAD ===")
print(run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git log --oneline -3 2>&1'))

print("\n=== BACKEND DB ===")
print(run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend printenv | grep DATABASE 2>&1"))

print("\n=== CAN CONNECT TO TENCENT MYSQL? ===")
print(run("timeout 5 mysql -h gz-cdb-nniq1lmp.sql.tencentcdb.com -P 27082 -u root -pxiaokang989aab -e 'SELECT 1' 2>&1 || echo 'no mysql client'"))

print("\n=== NETWORK ===")
print(run("docker network ls --filter name=6b099 2>&1"))

print("\n=== GIT REMOTE ===")
print(run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git remote -v 2>&1"))

c.close()
