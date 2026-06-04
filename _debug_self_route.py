import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd, t=120):
    print('>>>', cmd[:240])
    _, o, e = s.exec_command(cmd, timeout=t)
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    print(out[-4000:])
    if err:
        print('ERR:', err[-1500:])
    print('exit=', o.channel.recv_exit_status(), '\n')


print('--- 1) backend container 内部直接 curl /api/health-profile/self ---')
run(f'docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w "code=%{{http_code}}\\n" http://127.0.0.1:8000/api/health-profile/self')

print('--- 2) backend container 内部 curl /docs (确认应用本身在跑) ---')
run(f'docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w "code=%{{http_code}}\\n" http://127.0.0.1:8000/docs')

print('--- 3) 列出 main.py 里关于 health_profile_self 的注册 ---')
run(f'docker exec {DEPLOY_ID}-backend grep -n health_profile_self /app/app/main.py | head')

print('--- 4) 列出 health-profile 相关路由 ---')
run(
    f'docker exec {DEPLOY_ID}-backend python -c '
    f'\'from app.main import app; rs=[getattr(r,"path","") for r in app.routes]; '
    f'print([p for p in rs if "health-profile" in p])\''
)

print('--- 5) 看 backend logs 最近 60 行 ---')
run(f'docker logs --tail 80 {DEPLOY_ID}-backend 2>&1 | tail -80')

s.close()
