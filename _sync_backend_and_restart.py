"""把 backend 关键文件同步到服务器项目目录，然后 docker compose build/up backend。"""
import os, time, paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASS='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR=f"/home/ubuntu/{DEPLOY_ID}"
LOCAL = os.path.dirname(os.path.abspath(__file__))

# 含 trend_dates/trend_systolic/trend_diastolic 等新字段
FILES = [
    "backend/app/api/health_profile_v3.py",
    "backend/app/schemas/health_v3.py",
    "backend/tests/test_bp_card_optimize_v1_20260530.py",
    "backend/tests/test_bp_tab_trend_v1_20260530.py",
]

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = cli.open_sftp()

def ensure_dir(path):
    parts = path.strip('/').split('/'); cur=''
    for p in parts:
        cur = cur + '/' + p
        try: sftp.stat(cur)
        except IOError:
            try: sftp.mkdir(cur)
            except IOError: pass

for rel in FILES:
    local = os.path.join(LOCAL, rel.replace('/', os.sep))
    if not os.path.isfile(local):
        print('!! local missing', local); continue
    remote = f"{PROJECT_DIR}/{rel}"
    ensure_dir(os.path.dirname(remote))
    print(f'PUT {rel}')
    sftp.put(local, remote)
sftp.close()

def run(cmd, t=900):
    print(f"\n>>> {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=t, get_pty=True)
    out = o.read().decode(errors='replace'); err = e.read().decode(errors='replace')
    if out: print(out)
    if err: print('ERR:', err)
    rc = o.channel.recv_exit_status()
    print(f"<<< rc={rc}")
    return rc

run(f"cd {PROJECT_DIR} && docker compose build --no-cache backend 2>&1 | tail -n 60", t=1500)
run(f"cd {PROJECT_DIR} && docker compose up -d backend 2>&1 | tail -n 30")
time.sleep(8)
# 确认容器内代码确实更新（用 schemas 文件中的关键字段名）
run(f"docker exec {DEPLOY_ID}-backend bash -lc 'grep -c trend_systolic /app/app/schemas/health_v3.py'")
run(f"docker exec {DEPLOY_ID}-backend bash -lc 'grep -c trend_dates /app/app/api/health_profile_v3.py'")

# 重新装 pytest（重建后会丢失）
run(f"docker exec {DEPLOY_ID}-backend bash -lc 'pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -n 5'")
# 把测试文件也复制到容器内
run(f"docker cp {PROJECT_DIR}/backend/tests/test_bp_card_optimize_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/test_bp_card_optimize_v1_20260530.py")
run(f"docker cp {PROJECT_DIR}/backend/tests/test_bp_tab_trend_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/test_bp_tab_trend_v1_20260530.py")

# 跑两套测试
run(f"docker exec {DEPLOY_ID}-backend bash -lc 'cd /app && python -W ignore -m pytest tests/test_bp_card_optimize_v1_20260530.py tests/test_bp_tab_trend_v1_20260530.py -v 2>&1 | tail -n 40'", t=600)

cli.close()
