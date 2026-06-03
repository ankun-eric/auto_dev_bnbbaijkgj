"""[BUG_FIX 2026-05-29] 同步 main.py（其中含 self 路由注册）到容器并重启"""
import os
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))


s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)
sftp = s.open_sftp()


def run(cmd, t=300):
    print('>>>', cmd[:240])
    _, o, e = s.exec_command(cmd, timeout=t)
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    print(out[-4000:])
    if err:
        print('ERR:', err[-1500:])
    code = o.channel.recv_exit_status()
    print('exit=', code, '\n')
    return code


print('--- 1) 上传 main.py 到主机 ---')
sftp.put(os.path.join(LOCAL_ROOT, 'backend', 'app', 'main.py'),
         f'{PROJECT_DIR}/backend/app/main.py')

print('--- 2) docker cp 到容器 ---')
run(f'docker cp {PROJECT_DIR}/backend/app/main.py {DEPLOY_ID}-backend:/app/app/main.py')

print('--- 3) 重启 backend ---')
run(f'docker restart {DEPLOY_ID}-backend')

print('--- 4) 等待启动 ---')
for i in range(30):
    _, o, _ = s.exec_command(f'docker logs --tail 5 {DEPLOY_ID}-backend 2>&1 | tail -5', timeout=30)
    out = o.read().decode('utf-8', 'replace')
    if 'Application startup complete' in out or 'Uvicorn running' in out:
        print('  backend ready')
        break
    time.sleep(2)

print('--- 5) 验证路由注册 ---')
run(
    f'docker exec {DEPLOY_ID}-backend python -c '
    f'\'from app.main import app; print([getattr(r,"path","") for r in app.routes if "health-profile/self" in str(getattr(r,"path",""))])\''
)

print('--- 6) 健康检查 ---')
run(
    f'curl -sk -o /dev/null -w "code=%{{http_code}}\\n" '
    f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health-profile/self'
)

s.close()
