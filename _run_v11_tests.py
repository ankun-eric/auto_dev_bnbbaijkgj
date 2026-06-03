import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=20)
cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "python -m pytest "
    "tests/test_member_family_member_v11_20260530.py "
    "tests/test_family_member_state_machine_v1_20260529.py "
    "-v --tb=short --no-header -q 2>&1 | grep -E 'PASSED|FAILED|ERROR|test_|passed|failed' | head -50"
)
i, o, e = c.exec_command(cmd, timeout=200)
print(o.read().decode())
print('ERR:', e.read().decode())
c.close()
