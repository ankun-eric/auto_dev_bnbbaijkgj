"""Upload updated DB script and run it, test login."""
import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)

# Upload
sftp = c.open_sftp()
with open(r'C:\auto_output\bnbbaijkgj\deploy\db_init_async.py', 'rb') as f:
    sftp.putfo(f, '/tmp/db_init_async.py')
sftp.close()
print("Uploaded")

# Copy and run
c.exec_command('docker cp /tmp/db_init_async.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/db_init_async.py')
time.sleep(1)

i, o, e = c.exec_command('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 /app/db_init_async.py')
print(o.read().decode())

# Test login with phone
i, o, e = c.exec_command("""curl -s -k -X POST https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -H "Content-Type: application/json" -d '{"phone":"admin","password":"admin123"}'""")
print("Login test:", o.read().decode()[:300])

c.close()
