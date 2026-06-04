import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=15)

# Upload
local = r'C:\auto_output\bnbbaijkgj\deploy\chk_db.py'
sftp = c.open_sftp()
sftp.put(local, '/tmp/chk_db.py')
sftp.close()

# Run
si, so, se = c.exec_command('python3 /tmp/chk_db.py 2>&1', timeout=15)
out = so.read().decode('utf-8').strip()
err = se.read().decode('utf-8').strip()

print(out)
if err:
    print("ERR:", err)

c.close()
