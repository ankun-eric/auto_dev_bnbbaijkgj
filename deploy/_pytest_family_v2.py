"""上传最新测试文件并在 backend 容器中跑 pytest"""
import os
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJ = f'/home/ubuntu/{DEPLOY_ID}'
BACKEND = f'{DEPLOY_ID}-backend'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PWD, timeout=30, allow_agent=False, look_for_keys=False)

base = os.path.abspath(os.path.dirname(__file__) + '/..')
local_test = os.path.join(base, 'backend', 'tests', 'test_family_member_v2_20260518.py')
remote_test = f'{PROJ}/backend/tests/test_family_member_v2_20260518.py'

# 1) SFTP 上传最新测试文件
print(f'>>> upload {local_test} -> {remote_test}', flush=True)
sftp = c.open_sftp()
sftp.put(local_test, remote_test)
sftp.close()

cmds = [
    f"docker cp {remote_test} {BACKEND}:/app/tests/test_family_member_v2_20260518.py 2>&1",
    f"docker exec {BACKEND} bash -lc 'cd /app && python -m pytest tests/test_family_member_v2_20260518.py -v --tb=long --no-header -p no:warnings 2>&1'",
    f"docker exec {BACKEND} bash -lc 'cd /app && python -m pytest tests/test_family.py -q --tb=short 2>&1'",
]
for cmd in cmds:
    print(f"\n$ {cmd[:200]}", flush=True)
    _, out, err = c.exec_command(cmd, timeout=600)
    out_str = out.read().decode('utf-8', 'replace')
    err_str = err.read().decode('utf-8', 'replace')
    # 只打 tail
    print(out_str[-4000:] if len(out_str) > 4000 else out_str)
    if err_str.strip():
        print('STDERR:', err_str[-1500:])
    print('---')
c.close()
