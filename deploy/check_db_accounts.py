import paramiko, os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)
print('Connected', flush=True)

DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# Upload the db check script to server
local_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_db_script.py')
sftp = ssh.open_sftp()
sftp.put(local_script, '/tmp/check_db_script.py')
sftp.close()
print('Script uploaded', flush=True)

# Copy to container and execute
stdin, stdout, stderr = ssh.exec_command(
    f"docker cp /tmp/check_db_script.py {DID}-backend:/tmp/check_db_script.py", timeout=10)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')

stdin, stdout, stderr = ssh.exec_command(
    f"docker exec {DID}-backend python3 /tmp/check_db_script.py", timeout=30)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print("ERR:", err[:500])

ssh.close()
print("Done", flush=True)
