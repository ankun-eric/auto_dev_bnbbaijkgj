"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2] Repair backend container after rebuild

h5-web rebuild 似乎触发了 backend 镜像 rebuild，丢失了 v1 部署的几个文件。
重新把所有 v1+v2 涉及的 backend 文件全部 docker cp 进去并 restart。
"""
import sys, paramiko, time
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
BE=f'{DEPLOY_ID}-backend'
PROJ=f'/home/ubuntu/{DEPLOY_ID}'

# 所有 backend 文件
FILES = [
    # v1 文件
    ('backend/app/api/guardian_bugfix_v1.py',    '/app/app/api/guardian_bugfix_v1.py'),
    ('backend/app/api/family_management.py',     '/app/app/api/family_management.py'),
    ('backend/app/api/family.py',                '/app/app/api/family.py'),
    ('backend/app/api/guardian_system_v13.py',   '/app/app/api/guardian_system_v13.py'),
    ('backend/app/services/schema_sync.py',      '/app/app/services/schema_sync.py'),
    ('backend/app/main.py',                      '/app/app/main.py'),
    ('backend/app/models/models.py',             '/app/app/models/models.py'),
    # 测试
    ('backend/tests/test_guardian_bugfix_v1_20260529.py', '/app/tests/test_guardian_bugfix_v1_20260529.py'),
    ('backend/tests/test_guardian_bugfix_v2_20260529.py', '/app/tests/test_guardian_bugfix_v2_20260529.py'),
]

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=60,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=600):
    si,so,se=cli.exec_command(cmd,timeout=timeout)
    out=so.read().decode(errors='replace'); err=se.read().decode(errors='replace'); rc=so.channel.recv_exit_status()
    print('$',cmd[:200]); 
    if out.strip(): print(out[-3000:])
    if err.strip(): print('STDERR:',err[-800:])
    print('rc=',rc); return rc, out

# 1) 上传所有文件到主机（如果还在则覆盖）
print("=== 1. SFTP upload all files ===")
sftp = cli.open_sftp()
for local, container_dst in FILES:
    host_dst = f"{PROJ}/{local}"
    host_dir = host_dst.rsplit('/', 1)[0]
    r(f'mkdir -p {host_dir}')
    print(f"  upload {local} -> {host_dst}")
    sftp.put(local, host_dst)
sftp.close()

# 2) docker cp 全部文件
print("\n=== 2. docker cp all files ===")
for local, container_dst in FILES:
    host_dst = f"{PROJ}/{local}"
    r(f'docker cp {host_dst} {BE}:{container_dst}')

# 3) 重启
print("\n=== 3. restart backend ===")
r(f'docker restart {BE}')
time.sleep(8)
r(f'docker exec {BE} sh -c "wget -qO- http://localhost:8000/api/health 2>&1 || echo NR"')

# 4) 验证关键模块可 import
print("\n=== 4. verify imports ===")
r(f'docker exec {BE} python -c "from app.api.guardian_bugfix_v1 import reset_rate_limit_for_test; print(\'guardian_bugfix_v1 OK\')"')
r(f'docker exec {BE} python -c "from app.api.guardian_system_v13 import _calc_used_quota; print(\'_calc_used_quota OK\')"')

# 5) 跑测试
print("\n=== 5. run pytest ===")
rc, out = r(
    f'docker exec {BE} sh -c "cd /app && python -m pytest '
    f'tests/test_guardian_bugfix_v1_20260529.py '
    f'tests/test_guardian_bugfix_v2_20260529.py '
    f'-v --tb=short 2>&1 | tail -120"',
    timeout=900,
)
cli.close()
sys.exit(0 if rc == 0 else 2)
