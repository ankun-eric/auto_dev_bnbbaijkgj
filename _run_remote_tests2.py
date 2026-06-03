import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
inner = (
    'cd /app && python -m pytest '
    'tests/test_member_center_prd_v1_aligned.py::test_admin_membership_adjust_reset_quota '
    '-v --tb=long --no-header -p no:warnings 2>&1 | tail -50'
)
cmd = f"docker exec {DEPLOY_ID}-backend bash -c \"{inner}\""
stdin, stdout, stderr = c.exec_command(cmd, timeout=600)
out = stdout.read().decode('utf-8', errors='replace')
print(out)
c.close()
