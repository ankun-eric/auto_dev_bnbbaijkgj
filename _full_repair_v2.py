"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2] full repair: cp 全部业务依赖文件到 backend 容器"""
import sys, paramiko, time
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
BE=f'{DEPLOY_ID}-backend'
PROJ=f'/home/ubuntu/{DEPLOY_ID}'

# 必须 cp 的全部 backend 文件（main.py 引用的所有相对模块）
FILES = [
    'backend/app/api/guardian_bugfix_v1.py',
    'backend/app/api/health_profile_self.py',
    'backend/app/api/family_management.py',
    'backend/app/api/family.py',
    'backend/app/api/guardian_system_v13.py',
    'backend/app/services/schema_sync.py',
    'backend/app/main.py',
    'backend/app/models/models.py',
    'backend/tests/test_guardian_bugfix_v1_20260529.py',
    'backend/tests/test_guardian_bugfix_v2_20260529.py',
    'backend/tests/test_health_profile_self_complete_v1.py',
]

def to_container_path(local_path):
    # backend/app/... → /app/app/...
    # backend/tests/... → /app/tests/...
    if local_path.startswith('backend/'):
        return '/app/' + local_path[len('backend/'):]
    return None

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=60,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=600):
    si,so,se=cli.exec_command(cmd,timeout=timeout)
    out=so.read().decode(errors='replace'); err=se.read().decode(errors='replace'); rc=so.channel.recv_exit_status()
    print('$',cmd[:200]); 
    if out.strip(): print(out[-3000:])
    if err.strip(): print('STDERR:',err[-800:])
    print('rc=',rc); return rc, out

# 1) SFTP
print("=== SFTP upload ===")
sftp = cli.open_sftp()
for local in FILES:
    host_dst = f"{PROJ}/{local}"
    host_dir = host_dst.rsplit('/', 1)[0]
    r(f'mkdir -p {host_dir}')
    sftp.put(local, host_dst)
    print(f"  {local}")
sftp.close()

# 2) 等待容器恢复或者强制 stop+start
print("\n=== stop/wait/start ===")
r(f'docker stop {BE}', timeout=60)
time.sleep(2)
r(f'docker start {BE}', timeout=60)
time.sleep(3)

# 3) docker cp
print("\n=== docker cp ===")
for local in FILES:
    container_dst = to_container_path(local)
    if not container_dst: continue
    host_dst = f"{PROJ}/{local}"
    r(f'docker cp {host_dst} {BE}:{container_dst}')

# 4) 重启
print("\n=== restart ===")
r(f'docker restart {BE}')
time.sleep(10)

# 5) 健康检查
for i in range(20):
    rc, out = r(f'docker exec {BE} sh -c "python -c \\"import urllib.request; print(urllib.request.urlopen(\'http://localhost:8000/api/health\', timeout=3).read().decode())\\" 2>&1"', timeout=15)
    if rc == 0 and 'ok' in out.lower():
        print(f"[+] backend healthy after {i+1} polls")
        break
    time.sleep(2)

# 6) 安装 pytest（若需要）+ 跑测试
print("\n=== ensure pytest ===")
rc, _ = r(f'docker exec {BE} python -m pytest --version', timeout=30)
if rc != 0:
    r(f'docker exec {BE} pip install pytest pytest-asyncio aiosqlite httpx --quiet', timeout=300)

print("\n=== run pytest ===")
rc, out = r(
    f'docker exec {BE} sh -c "cd /app && python -m pytest '
    f'tests/test_guardian_bugfix_v1_20260529.py '
    f'tests/test_guardian_bugfix_v2_20260529.py '
    f'-v --tb=short 2>&1"',
    timeout=900,
)
cli.close()
sys.exit(0 if rc == 0 else 2)
