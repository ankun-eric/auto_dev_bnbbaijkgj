#!/usr/bin/env python3
import os, re, subprocess

BASE = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
os.chdir(BASE)

# Step 1: 安全预检 - 检查迁移脚本
print('=== 数据库变更安全预检 ===')
dangerous = False
patterns = ['drop_table', 'drop_column', 'drop_index', 'truncate', 'delete_from', 'alter_column']
for root, dirs, files in os.walk('.'):
    for fn in files:
        if 'migrations' in root and (fn.endswith('.py') or fn.endswith('.sql')):
            fp = os.path.join(root, fn)
            with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read().lower()
            for p in patterns:
                if p in content:
                    print(f'⚠️ 危险操作 {p} 发现于: {fp}')
                    dangerous = True

if dangerous:
    print('❌ 严重错误：检测到数据库迁移脚本包含 DROP / DELETE / TRUNCATE 等破坏性操作！')
    exit(1)
else:
    print('✅ 数据库迁移安全预检通过：未发现破坏性操作')

# Step 2: 检查数据库状态
print('\n=== 检查数据库状态 ===')
result = subprocess.run([
    'docker', 'exec', '6b099ed3-7175-4a78-91f4-44570c84ed27-backend',
    'python', '-c',
    'from app.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); tables = inspector.get_table_names(); print(len(tables)); print("\\n".join(sorted(tables)))'
], capture_output=True, text=True, timeout=60)
print(result.stdout)
if result.returncode != 0:
    print('数据库检测失败:', result.stderr)
    exit(1)

# Step 3: 执行迁移
lines = result.stdout.strip().split('\n')
table_count = int(lines[0]) if lines else 0
print(f'当前数据库表数量: {table_count}')

if table_count == 0:
    print('首次部署，执行完整建表...')
    r = subprocess.run([
        'docker', 'exec', '6b099ed3-7175-4a78-91f4-44570c84ed27-backend',
        'python', '-c',
        'from app.database import Base, engine; Base.metadata.create_all(bind=engine); print("建表完成")'
    ], capture_output=True, text=True, timeout=120)
    print(r.stdout)
else:
    print('数据库已有表，执行增量迁移...')
    r = subprocess.run([
        'docker', 'exec', '6b099ed3-7175-4a78-91f4-44570c84ed27-backend',
        'alembic', 'upgrade', 'head'
    ], capture_output=True, text=True, timeout=120)
    print(r.stdout if r.stdout else '无待执行迁移')
    if r.returncode != 0 and 'No migrations' not in r.stderr:
        print('Alembic 可能不可用，尝试直接建表...')
        r2 = subprocess.run([
            'docker', 'exec', '6b099ed3-7175-4a78-91f4-44570c84ed27-backend',
            'python', '-c',
            'from app.database import Base, engine; Base.metadata.create_all(bind=engine); print("建表完成")'
        ], capture_output=True, text=True, timeout=120)
        print(r2.stdout)

print('\n✅ 数据库迁移完成')
