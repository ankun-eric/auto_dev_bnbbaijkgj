import paramiko, os
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASSWORD='Newbang888'
REMOTE_BASE='/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
sftp = c.open_sftp()
files = [
    'backend/tests/test_home_safety_v2_revision.py',
    'backend/app/api/home_safety_v1.py',
    'admin-web/src/app/(admin)/home-safety/page.tsx',
]
for local in files:
    remote = f'{REMOTE_BASE}/{local}'
    print('local size:', os.path.getsize(local), local)
    sftp.put(local, remote)
print('uploaded')
local = 'backend/tests/test_home_safety_v2_revision.py'
remote = f'{REMOTE_BASE}/{local}'
# verify on remote
_, o, _ = c.exec_command(f"wc -l {remote}; sed -n '60,70p' {remote}")
print(o.read().decode('utf-8','replace'))
sftp.close(); c.close()
