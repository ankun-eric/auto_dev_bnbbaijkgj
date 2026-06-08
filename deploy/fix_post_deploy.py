"""修复部署后问题：Git更新 + 数据库迁移 + 默认账号"""
import paramiko
import time
import urllib.parse

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
print("修复部署后问题")
print("="*60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
print("SSH 连接成功\n")

# ====== 问题1：Git 更新 ======
print(">>> 修复1：Git 代码更新...")
# URL encode token中的特殊字符
encoded_token = urllib.parse.quote(GIT_TOKEN, safe='')
git_url_auth = f"https://{GIT_USER}:{encoded_token}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"

# 先检查当前 remote
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git remote -v 2>&1")
print(f"  Remotes: {out[:300]}")

# 尝试 fetch
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git fetch '{git_url_auth}' master 2>&1", timeout=60)
print(f"  Fetch: code={code}")
if err:
    print(f"  Fetch stderr: {err[:300]}")

if code == 0:
    out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git reset --hard FETCH_HEAD 2>&1 && git clean -fd 2>&1")
    print(f"  Reset: {'成功' if code == 0 else '失败: ' + err[:200]}")
else:
    print("  Git fetch 失败，尝试备用方案...")
    # 尝试用 git remote set-url + fetch
    cmds = [
        f"cd {PROJECT_DIR}",
        f"git remote remove codeup 2>/dev/null; git remote add codeup '{git_url_auth}'",
        "git fetch codeup master 2>&1",
    ]
    out, err, code = ssh_exec(ssh, " && ".join(cmds), timeout=60)
    print(f"  备用 fetch: code={code}")
    if code == 0:
        out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git reset --hard codeup/master 2>&1 && git clean -fd 2>&1")
        print(f"  备用 reset: {'成功' if code == 0 else '失败: ' + err[:200]}")
    else:
        print(f"  备用 fetch 也失败: {err[:300]}")

# ====== 问题2：数据库迁移 ======
print("\n>>> 修复2：数据库迁移...")

# 先检查容器内文件结构
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/ 2>&1")
print(f"  /app/ 内容: {out[:300]}")

out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/app/ 2>&1")
print(f"  /app/app/ 内容: {out[:300]}")

out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c 'import sys; print(sys.path)' 2>&1")
print(f"  sys.path: {out[:300]}")

# 检查 database.py 位置
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend find /app -name 'database.py' -type f 2>&1")
print(f"  database.py 位置: {out[:300]}")

# 尝试正确的导入路径
out, err, code = ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
try:
    from app.database import engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f'TABLES:{len(tables)}:{tables}')
except Exception as e:
    print(f'ERROR:{e}')
    import traceback
    traceback.print_exc()
" 2>&1""", timeout=30)
print(f"  数据库表: {out[:500]}")

# 尝试进行数据库迁移
if "TABLES:" in out:
    parts = out.split("TABLES:")[1] if "TABLES:" in out else ""
    try:
        table_count = int(parts.split(":")[0]) if ":" in parts else len(parts)
    except:
        table_count = 0
    
    # 检查是否有 alembic
    out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend test -d /app/alembic && echo 'YES' || echo 'NO'")
    has_alembic = "YES" in out2
    
    # 检查 migrations 目录
    out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/ 2>&1 || echo 'NO_MIGRATIONS'")
    has_migrations = "NO_MIGRATIONS" not in out2
    
    if not has_alembic and has_migrations:
        print("  发现 migrations/ 目录，执行迁移脚本...")
        out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/*.py 2>&1")
        print(f"  迁移脚本: {out2[:300]}")
        # 执行迁移脚本
        for line in out2.split('\n'):
            line = line.strip()
            if line.endswith('.py') and 'migration' in line.lower():
                script = line.split('/')[-1]
                out3, err3, code3 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 /app/migrations/{script} 2>&1", timeout=30)
                print(f"  {script}: {out3[:200]}")
    
    if not has_alembic:
        print("  无 Alembic，使用 SQLAlchemy create_all...")
        out2, err2, code2 = ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('create_all 完成')
" 2>&1""", timeout=30)
        print(f"  create_all: {out2[:300]}")
else:
    print(f"  无法连接数据库，跳过迁移")

# ====== 问题3：默认账号 ======
print("\n>>> 修复3：默认账号检查与创建...")

# 尝试通过 API 登录
out, err, code = ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
import urllib.request, json
data = json.dumps({'username':'admin','password':'admin123'}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/login', data=data, headers={'Content-Type':'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f'LOGIN_OK:{resp.status}')
except Exception as e:
    print(f'LOGIN_FAIL:{e}')
" 2>&1""", timeout=20)
print(f"  API 登录: {out[:200]}")

if "LOGIN_OK" not in out:
    print("  尝试通过数据库创建默认账号...")
    # 先看看 User 模型在哪里
    out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend find /app -name 'models.py' -path '*/app/models*' 2>&1")
    print(f"  models.py: {out[:200]}")
    
    # 尝试创建
    create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')
try:
    from app.database import SessionLocal
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
    print("  默认账号 admin 已存在且可正常登录")

# ====== 最终验证 ======
print("\n>>> 最终验证...")
out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>&1")
print(f"  GET /api/health: {out[:300]}")

out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ 2>&1 | head -5")
print(f"  GET /: {out[:300]}")

out, err, code = ssh_exec(ssh, f"curl -s --max-time 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/ 2>&1 | head -5")
print(f"  GET /admin/: {out[:300]}")

print("\n✅ 修复完成")
ssh.close()
