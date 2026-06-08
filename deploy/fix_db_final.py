"""数据库迁移 + 默认账号检查 (独立修复)"""
import paramiko, time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def ssh_exec(ssh, cmd, timeout=60):
    print(f"  [CMD] {cmd[:150]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return out.strip(), err.strip(), code

print("="*60)
print("数据库迁移与账号修复")
print("="*60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
print("SSH 连接成功\n")

# ====== 1. 探测数据库结构 ======
print(">>> 1. 探测后端容器数据库结构...")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c 'import sys; sys.path.insert(0,\"/app\"); import os; os.chdir(\"/app\"); from app.core.database import engine; from sqlalchemy import inspect; insp=inspect(engine); print(\"TABLES:\", len(insp.get_table_names()))' 2>&1", timeout=30)
print(f"  表数量: {out[:300]}")
if err:
    print(f"  STDERR: {err[:300]}")

# ====== 2. 执行增量迁移 ======
print("\n>>> 2. 执行增量迁移 (SQLAlchemy create_all)...")
out, err, code = ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys
sys.path.insert(0, '/app')
import os
os.chdir('/app')
from app.core.database import Base, engine
Base.metadata.create_all(bind=engine)
print('OK: create_all done')
" 2>&1""", timeout=30)
print(f"  create_all: {out[:300]}")
if err:
    print(f"  STDERR: {err[:300]}")

# ====== 3. 运行迁移脚本 ======
print("\n>>> 3. 运行迁移脚本...")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend ls /app/migrations/*.py 2>&1 || echo 'NONE'", timeout=15)
if "NONE" not in out:
    for line in out.split('\n'):
        line = line.strip()
        if line.endswith('.py'):
            fname = line.split('/')[-1]
            out2, err2, code2 = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 /app/migrations/{fname} 2>&1", timeout=30)
            print(f"  {fname}: {out2[:200]}")
else:
    print("  无迁移脚本")

# ====== 4. 检查并创建默认账号 ======
print("\n>>> 4. 默认账号检查与创建...")
create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys
sys.path.insert(0, '/app')
import os
os.chdir('/app')
from app.core.database import SessionLocal
from app.models.models import User
from app.core.security import get_password_hash

db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == 'admin').first()
    if existing:
        print('OK: admin exists')
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
        print('OK: admin created')
except Exception as e:
    db.rollback()
    print(f'ERR: {e}')
finally:
    db.close()
" 2>&1"""
out, err, code = ssh_exec(ssh, create_cmd, timeout=30)
print(f"  结果: {out[:500]}")
if err:
    print(f"  STDERR: {err[:500]}")

# ====== 5. 验证 ======
print("\n>>> 5. 验证数据库状态...")
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c \"import sys; sys.path.insert(0,'/app'); import os; os.chdir('/app'); from app.core.database import engine; from sqlalchemy import inspect; insp=inspect(engine); tabs=insp.get_table_names(); print(f'Tables: {len(tabs)}'); [print(f'  {t}') for t in sorted(tabs)[:30]]\" 2>&1", timeout=30)
print(f"  {out[:600]}")

print("\n✅ 数据库修复完成")
ssh.close()
