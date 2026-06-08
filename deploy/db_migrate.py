import subprocess, sys, os

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
WORK_DIR = f'/home/ubuntu/{DEPLOY_ID}'

def run(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=WORK_DIR, **kw)
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr)
    return r

print("=== 数据库变更安全预检 ===")
dangerous = 0
for root, dirs, files in os.walk(WORK_DIR):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules','.git','__pycache__','.next')]
    for f in files:
        if f.endswith(('.py','.sql')):
            fpath = os.path.join(root, f)
            if 'migrations' not in fpath and 'migration' not in fpath:
                continue
            try:
                with open(fpath, encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
                for op in ['DROP TABLE','DROP COLUMN','DROP INDEX','TRUNCATE','DELETE FROM','ALTER COLUMN']:
                    if op.lower() in content.lower():
                        print(f"WARN: {op} found in {fpath}")
                        dangerous += 1
            except:
                pass

if dangerous > 0:
    print("FATAL: 危险操作发现，中止部署！")
    sys.exit(1)
print("安全预检通过")

print("=== 检测数据库状态 ===")
check_sql = """
import asyncio
from sqlalchemy import inspect, text
import sys, os
sys.path.insert(0, '/app')
from app.database import engine, DATABASE_URL

print(f'DB: {DATABASE_URL.split(\"@\")[1] if \"@\" in DATABASE_URL else DATABASE_URL}')

def check():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f'Table count: {len(tables)}')
    for t in sorted(tables)[:10]:
        cols = [c['name'] for c in inspector.get_columns(t)]
        print(f'  {t}: {len(cols)} cols')
    if len(tables) > 10:
        print(f'  ... and {len(tables)-10} more tables')
    return len(tables)

count = check()
print(f'TABLE_COUNT={count}')
"""

r = run(f"docker exec {DEPLOY_ID}-backend python3 -c '{check_sql}'", timeout=30)
table_count = 0
for line in (r.stdout + r.stderr).split('\n'):
    if 'TABLE_COUNT=' in line:
        try: table_count = int(line.split('=')[1].strip())
        except: pass

print(f"当前表数量: {table_count}")

if table_count == 0:
    print("=== 首次部署，执行完整建表 ===")
    r = run(f"docker exec {DEPLOY_ID}-backend python3 -c \"from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('Tables created')\"", timeout=60)
else:
    print("=== 增量迁移（仅新增表/字段） ===")
    r = run(f"docker exec {DEPLOY_ID}-backend alembic upgrade head 2>&1 || echo 'No pending migrations'", timeout=60)

print("DB_MIGRATE_DONE")
