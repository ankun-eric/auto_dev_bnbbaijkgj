"""[BUG_FIX 2026-05-29] 容器在 restart loop。
策略：
1. 把更稳健的 main.py（importlib + try/except）上传到主机
2. docker stop 后用 docker create 一个新容器把文件 cp 进去，然后 start
   或更简单：docker cp 到 stopped 容器后启动（实际上 restart loop 期间 docker cp 会失败，所以先 stop）
"""
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
    print(out[-3000:])
    if err:
        print('ERR:', err[-1500:])
    code = o.channel.recv_exit_status()
    print('exit=', code, '\n')
    return code, out


print('--- 1) 上传修订版 main.py 到主机 ---')
sftp.put(os.path.join(LOCAL_ROOT, 'backend', 'app', 'main.py'),
         f'{PROJECT_DIR}/backend/app/main.py')

print('--- 2) docker stop（强制结束 restart loop） ---')
run(f'docker stop {DEPLOY_ID}-backend', t=60)

print('--- 3) docker cp main.py + health_profile_self.py 到容器 ---')
run(f'docker cp {PROJECT_DIR}/backend/app/main.py {DEPLOY_ID}-backend:/app/app/main.py')
run(f'docker cp {PROJECT_DIR}/backend/app/api/health_profile_self.py {DEPLOY_ID}-backend:/app/app/api/health_profile_self.py')

print('--- 4) docker start ---')
run(f'docker start {DEPLOY_ID}-backend')

print('--- 5) 等待启动 ---')
ready = False
for i in range(40):
    _, out = run(f'docker logs --tail 5 {DEPLOY_ID}-backend 2>&1 | tail -5')
    if 'Application startup complete' in out or 'Uvicorn running' in out:
        ready = True
        print('  backend ready')
        break
    if 'Traceback' in out and 'ImportError' in out:
        print('  IMPORTERROR DETECTED')
        break
    time.sleep(3)
if not ready:
    print('  backend NOT ready in 120s, last log:')
    run(f'docker logs --tail 80 {DEPLOY_ID}-backend 2>&1 | tail -80')

print('--- 6) 验证路由 ---')
run(
    f'docker exec {DEPLOY_ID}-backend python -c '
    f'\'from app.main import app; print([getattr(r,"path","") for r in app.routes if "health-profile/self" in str(getattr(r,"path",""))])\''
)

print('--- 7) 健康检查 ---')
run(
    f'curl -sk -o /dev/null -w "code=%{{http_code}}\\n" '
    f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health-profile/self'
)

s.close()
