import paramiko, sys

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

cmd = (
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc '
    '"cd /app && python -m pytest -x -q '
    'tests/test_home_safety_alarm_resolve_v2_20260529.py '
    'tests/test_home_safety_remark_alarms_v1_20260529.py '
    '--maxfail=5 2>&1 | tail -120"'
)
print('>>>', cmd)
stdin, stdout, stderr = s.exec_command(cmd, timeout=600)
out = stdout.read().decode('utf-8', 'replace')
err = stderr.read().decode('utf-8', 'replace')
print(out)
if err:
    print('STDERR:', err)
code = stdout.channel.recv_exit_status()
print('exit=', code)
sys.exit(0 if 'failed' not in out.lower() or 'passed' in out.lower() else 1)
