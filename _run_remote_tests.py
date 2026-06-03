import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
inner = (
    'cd /app && '
    'pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -5 && '
    'python -m pytest tests/test_member_center_prd_v1_aligned.py -v --tb=short 2>&1 | tail -120'
)
cmd = f"docker exec {DEPLOY_ID}-backend bash -c \"{inner}\""
print('cmd len:', len(cmd))
stdin, stdout, stderr = c.exec_command(cmd, timeout=600)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err.strip():
    print('STDERR:\n', err)
c.close()
