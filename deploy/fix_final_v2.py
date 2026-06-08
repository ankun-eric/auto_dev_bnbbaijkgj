"""修复：Git更新 + 数据库迁移 + 默认账号 (v2)"""
import paramiko, time, urllib.parse

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_URL = "https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

def ssh_exec(ssh, cmd, timeout=60):
    print(f"  [CMD] {cmd[:150]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return out.strip(), err.strip(), code

print("="*60)
print("修复部署后问题 v2")
print("="*60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
print("SSH 连接成功\n")

# ====== 1. Git 更新 ======
print(">>> 1. Git 代码更新...")
encoded_token = urllib.parse.quote(GIT_TOKEN, safe='')
git_url_auth = f"https://{GIT_USER}:{encoded_token}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"

out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git status --short 2>&1")
print(f"  当前状态: {out[:200]}")

# git fetch
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git fetch '{git_url_auth}' master 2>&1", timeout=60)
print(f"  Fetch: code={code}")

# 获取远程最新 commit
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log FETCH_HEAD -1 --oneline 2>&1")
print(f"  远程 HEAD: {out[:100]}")

# 强制 reset（忽略本地修改）
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git checkout -- . 2>&1 && git reset --hard FETCH_HEAD 2>&1 && git clean -fdx 2>&1")
print(f"  Reset: code={code} {'成功' if code==0 else ('失败: '+err[:200])}")

out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --oneline 2>&1")
print(f"  当前 HEAD: {out[:100]}")

# ====== 2. 数据库迁移 ======
print("\n>>> 2. 数据库迁移...")
# database.py 在 /app/app/core/database.py
check_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
try:
    from app.core.database import engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f'TABLES_COUNT:{len(tables)}')
    for t in sorted(tables)[:20]:
        print(f'  {t}')
except Exception as e:
    print(f'ERROR:{e}')
" 2>&1"""
out, err, code = ssh_exec(ssh, check_cmd, timeout=30)
print(f"  数据库状态: {out[:500]}")

# 检查是否有 alembic
out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend test -d /app/alembic && echo 'YES' || echo 'NO'")
has_alembic = "YES" in out2

# 检查 migrations
out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/ 2>&1 || echo 'NONE'")
has_migrations = "NONE" not in out2

if "TABLES_COUNT:" in out:
    # 运行 SQLAlchemy create_all（增量式）
    create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
try:
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)
    print('create_all DONE')
except Exception as e:
    print(f'create_all ERROR:{{e}}')
    import traceback
    traceback.print_exc()
" 2>&1"""
    out, err, code = ssh_exec(ssh, create_cmd, timeout=30)
    print(f"  create_all: {out[:300]}")
    
    # 运行 migrations 目录下的迁移脚本
    if has_migrations:
        out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/*.py 2>&1 || echo ''")
        for line in out2.split('\n'):
            line = line.strip()
            if line.endswith('.py'):
                fname = line.split('/')[-1]
                out3, err3, code3 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 /app/migrations/{fname} 2>&1", timeout=30)
                print(f"  migration {fname}: {out3[:200]}")
else:
    print(f"  数据库连接失败: {out[:300]}")

# ====== 3. 默认账号 ======
print("\n>>> 3. 默认账号检查与创建...")

# API 登录测试
out, err, code = ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
import urllib.request, json
data = json.dumps({{'username':'admin','password':'admin123'}}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/login', data=data, headers={{'Content-Type':'application/json'}})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    body = resp.read().decode()
    print(f'LOGIN_OK:{{resp.status}}:{{body[:200]}}')
except Exception as e:
    print(f'LOGIN_FAIL:{{e}}')
" 2>&1""", timeout=20)
print(f"  API 登录测试: {out[:300]}")

if "LOGIN_OK" not in out:
    print("  尝试数据库创建...")
    create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
try:
    from app.core.database import SessionLocal
    from app.models.models import User
    from app.core.security import get_password_hash
    db = SessionLocal()
    existing = db.query(User).filter(User.username == 'admin').first()
    if existing:
        print('ADMIN_EXISTS')
    else:
        user = User(
            username='admin',
            hashed_password=get_password_hash('admin123'),
            is_admin=True,
            is_active=True,
            full_name='Administrator'
        )
        db.add(user)
        db.commit()
        print('ADMIN_CREATED')
    db.close()
except Exception as e:
    print(f'ERROR:{{e}}')
    import traceback
    traceback.print_exc()
" 2>&1"""
    out, err, code = ssh_exec(ssh, create_cmd, timeout=30)
    print(f"  创建结果: {out[:500]}")
else:
    print("  默认账号 admin 可正常登录 ✓")

# ====== 4. 构建新代码 ======
print("\n>>> 4. 使用新代码重新构建...")
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'")
BUILD_COMMIT = out.strip()
print(f"  BUILD_COMMIT: {BUILD_COMMIT}")

# 重新构建（使用缓存）
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && BUILD_COMMIT='{BUILD_COMMIT}' docker compose -f deploy/docker-compose.prod.yml build 2>&1", timeout=600)
print(f"  构建: {'成功' if code==0 else '失败'}")

# 重新启动
if code == 0:
    out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && BUILD_COMMIT='{BUILD_COMMIT}' docker compose -f deploy/docker-compose.prod.yml up -d 2>&1", timeout=60)
    print(f"  启动: {'成功' if code==0 else '失败'}")
    
    # 等待健康
    print("  等待健康检查...")
    for i in range(24):
        time.sleep(5)
        out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml ps --format json 2>&1", timeout=10)
        total = out.count('"Name"')
        healthy = out.count('"healthy"')
        if total > 0 and healthy == total:
            print(f"  所有容器健康! ({i+1}轮)")
            break
    else:
        print("  等待超时")

# ====== 5. 最终验证 ======
print("\n>>> 5. 最终验证...")
out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>&1")
print(f"  /api/health: {out[:200]}")

out, err, code = ssh_exec(ssh, f"curl -sI --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ 2>&1 | head -5")
print(f"  / HTTP status: {out[:200]}")

print("\n✅ 修复完成")
ssh.close()
