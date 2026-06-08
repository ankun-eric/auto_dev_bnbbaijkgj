#!/usr/bin/env python3
"""Fix database connection issue"""
import paramiko, time, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=30):
    print(f'\n[CMD] {cmd[:200]}')
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f'[OUT] {out.strip()[:800]}')
    if err.strip():
        print(f'[ERR] {err.strip()[:400]}')
    sys.stdout.flush()
    return out, err, code

# 1. Check if db container exists and its networks
print("=" * 60)
print("1. DB Container Check")
print("=" * 60)
run("docker ps -a --filter name=db --format '{{.Names}} {{.Status}}'")
run("docker inspect db --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>&1")

# 2. Check project network and what containers are on it
print("\n" + "=" * 60)
print("2. Project Network")
print("=" * 60)
run("docker network inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-network --format '{{range .Containers}}{{.Name}} {{end}}'")

# 3. Check if db is running
print("\n" + "=" * 60)
print("3. DB Running?")
print("=" * 60)
run("docker port db 2>&1")
run("docker exec db mysqladmin ping -h localhost -u root -pbini_health_2026 2>&1")

# 4. Get db container's IP
print("\n" + "=" * 60)
print("4. DB IP Address")
print("=" * 60)
run("docker inspect db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' 2>&1")

# 5. Check backend's DATABASE_URL in docker-compose
print("\n" + "=" * 60)
print("5. DATABASE_URL in compose")
print("=" * 60)
run("grep DATABASE_URL /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/deploy/docker-compose.prod.yml")

# 6. Stop backend temporarily and test connectivity from another container on same network
print("\n" + "=" * 60)
print("6. Test connectivity from project network")
print("=" * 60)
run("docker run --rm --network 6b099ed3-7175-4a78-91f4-44570c84ed27-network alpine ping -c 2 db 2>&1 || echo 'ping failed'", timeout=15)
run("docker run --rm --network 6b099ed3-7175-4a78-91f4-44570c84ed27-network alpine nslookup db 2>&1 || echo 'dns failed'", timeout=15)

# 7. Get full backend error log
print("\n" + "=" * 60)
print("7. Full backend error")
print("=" * 60)
run("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -60", timeout=15)

ssh.close()
print("\nDone!")
