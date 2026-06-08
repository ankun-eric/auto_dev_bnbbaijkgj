"""Upload and run DB init script on server."""
import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)

# Upload via SFTP
sftp = c.open_sftp()
with open(r'C:\auto_output\bnbbaijkgj\deploy\db_init_async.py', 'rb') as f:
    sftp.putfo(f, '/tmp/db_init_async.py')
sftp.close()
print("Uploaded")

# Copy into container
i, o, e = c.exec_command('docker cp /tmp/db_init_async.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/db_init_async.py')
o.read(); e.read()
time.sleep(1)

# Run
i, o, e = c.exec_command('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 /app/db_init_async.py 2>&1')
out = o.read().decode()
err = e.read().decode()
print("STDOUT:", out)
print("STDERR:", err[:500])

# Also check admin login
i, o, e = c.exec_command('curl -s -k -X POST https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" 2>&1')
print("Login test:", o.read().decode()[:300])

# Container status
i, o, e = c.exec_command('docker ps --filter name=6b099ed3 --format "{{.Names}} {{.Status}}"')
print("Containers:", o.read().decode())

c.close()
