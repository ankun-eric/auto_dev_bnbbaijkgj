import sys, paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
BE=f'{DEPLOY_ID}-backend'

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=60,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=900):
    si,so,se=cli.exec_command(cmd,timeout=timeout)
    out=so.read().decode(errors='replace'); err=se.read().decode(errors='replace'); rc=so.channel.recv_exit_status()
    print('$',cmd[:200]); 
    if out.strip(): print(out[-12000:])
    if err.strip(): print('STDERR:',err[-1500:])
    print('rc=',rc); return rc, out

# 仅跑 v2
rc, out = r(
    f'docker exec {BE} sh -c "cd /app && python -m pytest '
    f'tests/test_guardian_bugfix_v2_20260529.py '
    f'-v --tb=long --no-header 2>&1"',
)

# 看一个 v1 的失败原因
print('\n\n=== v1 single test ===')
r(f'docker exec {BE} sh -c "cd /app && python -m pytest tests/test_guardian_bugfix_v1_20260529.py::test_tc_inv_01_invite_without_nickname_returns_422 -v --tb=long --no-header 2>&1"')

cli.close()
