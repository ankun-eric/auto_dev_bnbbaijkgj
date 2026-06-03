"""[BUG_FIX 2026-05-29] 排查测试文件路径并执行"""
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
    return code, o


run(f'docker exec {DEPLOY_ID}-backend bash -lc "ls /app/tests/test_health_profile* 2>&1"')
run(f'docker exec {DEPLOY_ID}-backend bash -lc "find /app -name test_health_profile_self_complete_v1.py 2>&1"')
# 重新拷贝（保险）
run(f'docker cp /home/ubuntu/{DEPLOY_ID}/backend/tests/test_health_profile_self_complete_v1.py {DEPLOY_ID}-backend:/app/tests/test_health_profile_self_complete_v1.py 2>&1')
run(f'docker exec {DEPLOY_ID}-backend bash -lc "ls -la /app/tests/test_health_profile_self_complete_v1.py 2>&1"')
run(
    f'docker exec {DEPLOY_ID}-backend bash -lc '
    f'"cd /app && python -m pytest tests/test_health_profile_self_complete_v1.py -v --tb=short -p no:warnings 2>&1 | tail -120"',
    t=600,
)
s.close()
