"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2] 重新 cp + 跑测试"""
import sys, paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
BE=f'{DEPLOY_ID}-backend'
PROJ=f'/home/ubuntu/{DEPLOY_ID}'

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=60,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=300):
    si,so,se=cli.exec_command(cmd,timeout=timeout)
    out=so.read().decode(errors='replace'); err=se.read().decode(errors='replace'); rc=so.channel.recv_exit_status()
    print('$',cmd[:200]); 
    if out.strip(): print(out[-5000:])
    if err.strip(): print('STDERR:',err[-1000:])
    print('rc=',rc); return rc, out

# 1. 重新 docker cp
r(f'docker cp {PROJ}/backend/tests/test_guardian_bugfix_v1_20260529.py {BE}:/app/tests/test_guardian_bugfix_v1_20260529.py')
r(f'docker cp {PROJ}/backend/tests/test_guardian_bugfix_v2_20260529.py {BE}:/app/tests/test_guardian_bugfix_v2_20260529.py')
r(f'docker cp {PROJ}/backend/app/api/guardian_system_v13.py {BE}:/app/app/api/guardian_system_v13.py')

# 2. 检查 pytest 是否还在（rebuild 后镜像是不同的，但 backend 容器只 restart，不 rebuild，所以 pytest 还在）
r(f'docker exec {BE} sh -c "python -m pytest --version 2>&1"')

# 3. 如未装则装
rc, out = r(f'docker exec {BE} sh -c "python -m pytest --version 2>&1"')
if rc != 0:
    r(f'docker exec {BE} pip install pytest pytest-asyncio aiosqlite httpx --quiet', timeout=300)

# 4. 重启 backend 让代码生效
r(f'docker restart {BE}')
import time; time.sleep(8)

# 5. 跑测试
rc, out = r(
    f'docker exec {BE} sh -c "cd /app && python -m pytest '
    f'tests/test_guardian_bugfix_v1_20260529.py '
    f'tests/test_guardian_bugfix_v2_20260529.py '
    f'-v --tb=short 2>&1"',
    timeout=900,
)
cli.close()
sys.exit(0 if rc==0 else 2)
