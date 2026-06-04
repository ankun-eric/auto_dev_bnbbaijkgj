"""[BUG_FIX 2026-05-29] 安全策略：
- 容器镜像里 main.py 是旧版本（没有 health_profile_self / guardian_bugfix_v1 等新模块导入）
- 直接覆盖会因 ImportError 让容器进入 restart loop
- 正确做法：在镜像里 main.py 的末尾追加一段独立的路由注册（用 importlib + try/except 兜底），
  并把 health_profile_self.py 文件 cp 进去
- 这样保持容器健康启动，同时新增 /api/health-profile/self 路由
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


# 1. 读取 image 中 main.py 的内容（已 docker cp 到 /tmp/img_main.py）
img_main_local = os.path.join(LOCAL_ROOT, '_img_main.py')
with open(img_main_local, 'rb') as f:
    img_content = f.read()

# 2. 在 image main.py 末尾追加路由注册（importlib + try/except）
patch_block = '''

# [BUG_FIX 2026-05-29] /api/health-profile/self 路由注册（追加补丁，importlib 动态加载 + 异常兜底）
# 此块独立成段，避免修改顶部 from app.api import (...) 列表，从而最大限度兼容当前镜像。
try:
    import importlib as _importlib_self_complete  # noqa: E402
    _hp_self_mod = _importlib_self_complete.import_module("app.api.health_profile_self")
    app.include_router(_hp_self_mod.router)
    import logging as _lg_self_complete
    _lg_self_complete.getLogger("app.startup").info(
        "[health_profile_self] router registered at /api/health-profile/self"
    )
except Exception as _e_self_complete:
    import logging as _lg_self_complete2
    _lg_self_complete2.getLogger("app.startup").error(
        "[health_profile_self] register failed: %s", _e_self_complete
    )
'''.encode('utf-8')

patched = img_content + patch_block
patched_path = os.path.join(LOCAL_ROOT, '_patched_main.py')
with open(patched_path, 'wb') as f:
    f.write(patched)
print(f'patched main.py written: {len(patched)} bytes (orig {len(img_content)})')

# 3. 上传 patched main.py 到主机
sftp.put(patched_path, f'{PROJECT_DIR}/_patched_main_20260529.py')

# 4. 容器在 restart loop。先 stop，cp 文件，再 start
run(f'docker stop {DEPLOY_ID}-backend', t=60)

# 5. cp 进容器
run(f'docker cp {PROJECT_DIR}/_patched_main_20260529.py {DEPLOY_ID}-backend:/app/app/main.py')
run(f'docker cp {PROJECT_DIR}/backend/app/api/health_profile_self.py {DEPLOY_ID}-backend:/app/app/api/health_profile_self.py')

# 6. start
run(f'docker start {DEPLOY_ID}-backend')

# 7. 等待
print('--- 等待启动 ---')
ready = False
for i in range(40):
    _, out = run(f'docker logs --tail 5 {DEPLOY_ID}-backend 2>&1 | tail -5')
    if 'Application startup complete' in out or 'Uvicorn running' in out:
        ready = True
        print('  ready')
        break
    if 'Traceback' in out and ('ImportError' in out or 'SyntaxError' in out):
        print('  STARTUP FAILED')
        break
    time.sleep(3)
if not ready:
    run(f'docker logs --tail 80 {DEPLOY_ID}-backend 2>&1 | tail -80')

# 8. 验证路由
run(
    f'docker exec {DEPLOY_ID}-backend python -c '
    f'\'from app.main import app; print([getattr(r,"path","") for r in app.routes if "health-profile/self" in str(getattr(r,"path",""))])\''
)

# 9. 健康检查
run(
    f'curl -sk -o /dev/null -w "code=%{{http_code}}\\n" '
    f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health-profile/self'
)

# 10. 清理临时容器
run(f'docker rm -f tmp_extract_be tmp_extract_be2 2>&1 || true')

s.close()
