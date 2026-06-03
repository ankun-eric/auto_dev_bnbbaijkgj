import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE = f'/home/ubuntu/{DEPLOY_ID}'

sftp = c.open_sftp()
sftp.put(
    r'C:\auto_output\bnbbaijkgj\backend\tests\test_member_center_prd_v1_aligned.py',
    f'{REMOTE}/backend/tests/test_member_center_prd_v1_aligned.py',
)
sftp.close()

# copy into container
c.exec_command(
    f"docker cp {REMOTE}/backend/tests/test_member_center_prd_v1_aligned.py "
    f"{DEPLOY_ID}-backend:/app/tests/test_member_center_prd_v1_aligned.py"
)[1].read()

# run full suite
inner = (
    'cd /app && python -m pytest tests/test_member_center_prd_v1_aligned.py '
    '-v --tb=short -p no:warnings 2>&1 | tail -40'
)
cmd = f"docker exec {DEPLOY_ID}-backend bash -c \"{inner}\""
stdin, stdout, stderr = c.exec_command(cmd, timeout=300)
print(stdout.read().decode('utf-8', errors='replace'))
c.close()
