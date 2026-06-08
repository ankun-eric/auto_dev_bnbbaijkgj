#!/usr/bin/env python3
"""Find the correct MySQL database with bini_health database"""
import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=30):
    print('\n[CMD] ' + cmd[:200])
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        print('[OUT] ' + out.strip()[:800])
    if err.strip():
        print('[ERR] ' + err.strip()[:400])
    sys.stdout.flush()
    return out, err

# Check noob_ai-db image and environment
print("=" * 60)
print("1. noob_ai-db container details")
print("=" * 60)
run("docker inspect noob_ai-db --format 'Image: {{.Config.Image}}'")
run("docker inspect noob_ai-db --format '{{range .Config.Env}}{{.}} {{end}}' 2>&1 | tr ' ' '\n' | grep -i mysql\|mariadb\|pass\|root | head -20")

# Check if it's actually MySQL
print("\n" + "=" * 60)
print("2. Try connecting with different methods")
print("=" * 60)
# Try to see what process is running in noob_ai-db
run("docker top noob_ai-db 2>&1 | head -5")

# Check the network of noob_ai-db
print("\n" + "=" * 60)
print("3. noob_ai-db network details")
print("=" * 60)
run("docker inspect noob_ai-db --format '{{json .NetworkSettings.Networks}}' 2>&1 | python3 -m json.tool 2>/dev/null | head -20")

# Try connecting via 622c312c-mysql (which has host port 32770)
print("\n" + "=" * 60)
print("4. Try 622c312c-mysql via host port")
print("=" * 60)
run("mysql -h 127.0.0.1 -P 32770 -u root -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -20")

# Try via Docker network for 622c312c-mysql
print("\n" + "=" * 60)
print("5. Connect 622c312c-mysql to project network and try")
print("=" * 60)
run("docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network 622c312c-ea3e-4c32-af33-9836db929371-mysql 2>&1 || echo 'already'")
# Use mysql client from 622c312c project to check its own db
run("docker exec 622c312c-ea3e-4c32-af33-9836db929371-mysql mysql -u root -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -20")
# Check what password 622c312c mysql uses
run("docker inspect 622c312c-ea3e-4c32-af33-9836db929371-mysql --format '{{range .Config.Env}}{{.}} {{end}}' 2>&1 | tr ' ' '\n' | grep -i pass\|root | head -10")

# Now check if we can use host.docker.internal or gateway
print("\n" + "=" * 60)
print("6. Check other MySQL containers for bini_health")
print("=" * 60)
# Check 1f2b22da-db
run("docker exec 1f2b22da-528e-4e13-acee-6511a7b5b172-db mysql -u root -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -20")

# Check 0451a430-db
run("docker exec 0451a430-e3c8-49e2-b627-329938d2313d-db mysql -u root -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -20")

ssh.close()
print("\nDone!")
