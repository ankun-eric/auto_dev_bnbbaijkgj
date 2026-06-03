"""[BUG_FIX 2026-05-29] 在远程容器中运行 health_profile_self 测试"""
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd, t=600):
    print('\n>>>', cmd[:240])
    _, out, err = s.exec_command(cmd, timeout=t)
    o = out.read().decode('utf-8', 'replace')
    e = err.read().decode('utf-8', 'replace')
    code = out.channel.recv_exit_status()
    print(o[-15000:])
    if e:
        print('STDERR:', e[-3000:])
    print('[exit=', code, ']')
    return code, o, e


run(f'docker exec {DEPLOY_ID}-backend pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -20', t=300)
run(f'docker exec {DEPLOY_ID}-backend bash -lc "cd /app && ls tests/ 2>&1 | head -40"')
run(f'docker exec {DEPLOY_ID}-backend bash -lc "cd /app && head -60 tests/conftest.py 2>&1"')
run(
    f'docker exec {DEPLOY_ID}-backend bash -lc '
    f'"cd /app && python -m pytest tests/test_health_profile_self_complete_v1.py -v --tb=short --no-header 2>&1 | tail -200"',
    t=600,
)
s.close()
