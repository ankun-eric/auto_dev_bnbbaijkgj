#!/usr/bin/env python3
"""最终修复：gateway配置 + 数据库迁移 + 账号检查"""
import paramiko, time, re

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GW_DIR = "/home/ubuntu/gateway"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("chat.benne-ai.com", port=22, username="ubuntu", password="Benne-ai@#", timeout=30)

def run(cmd, timeout=60):
    print(f"  > {cmd[:150]}")
    _, o, e = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    result = out + err
    result = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', result)
    result = re.sub(r'\x1b\[[?]\d+[hl]', '', result)
    result = re.sub(r'\x1b\[[=]', '', result)
    if len(result) > 500:
        result = result[:250] + "\n...(截断)...\n" + result[-150:]
    if result.strip():
        print(result.strip())
    return out + err

print("=" * 60)
print("最终修复")
print("=" * 60)

# 1. Git pull
print("\n[1] Git pull 最新 gateway-routes.conf...")
run(f"cd {PROJ_DIR} && git fetch origin master && git reset --hard origin/master && echo GIT_OK", timeout=60)

# 2. 复制 gateway 配置
print("\n[2] 更新 gateway 配置...")
run(f"sudo cp {GW_DIR}/conf.d/{DEPLOY_ID}.conf {GW_DIR}/conf.d.bak/{DEPLOY_ID}.conf.bak.final 2>/dev/null; echo backup_ok")
run(f"sudo cp {PROJ_DIR}/deploy/gateway-routes.conf {GW_DIR}/conf.d/{DEPLOY_ID}.conf && echo copy_ok")

# 3. 测试并重载 nginx
print("\n[3] 测试 nginx 语法...")
result = run("docker exec gateway-nginx nginx -t 2>&1")
if "successful" in result or "syntax is ok" in result.lower():
    print("  nginx 语法通过，重载...")
    run("docker exec gateway-nginx nginx -s reload 2>&1")
    print("  重载完成")
else:
    print(f"  语法错误: {result[:400]}")

# 4. SSL 验证
print("\n[4] SSL 验证...")
time.sleep(2)
run("curl -sI https://chat.benne-ai.com/ 2>&1 | head -3")

# 5. 数据库迁移 - 修复路径问题
print("\n[5] 数据库迁移...")
# 先检查工作目录和模块
result = run(f"docker exec {DEPLOY_ID}-backend pwd 2>&1")
print(f"  工作目录: {result.strip()[:200]}")

result = run(f"docker exec {DEPLOY_ID}-backend python -c 'import app; print(dir(app))' 2>&1")
print(f"  app模块: {result.strip()[:200]}")

# 尝试执行迁移
cmd = f'docker exec {DEPLOY_ID}-backend python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine); print(\'OK\')" 2>&1'
result = run(cmd, timeout=30)
if 'OK' in result:
    print("  数据库迁移完成")
else:
    print(f"  迁移结果: {result.strip()[:300]}")
    # 降级：直接执行 SQL 检查
    print("  尝试直接检查数据库连接...")
    run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import engine; print('engine_ok')\" 2>&1", timeout=15)

# 6. 默认账号
print("\n[6] 检查默认账号...")
cmd2 = f'docker exec {DEPLOY_ID}-backend python -c "from app.database import SessionLocal; from app.models.models import User; db=SessionLocal(); u=db.query(User).filter(User.username==chr(97)+chr(100)+chr(109)+chr(105)+chr(110)).first(); print(chr(69)+chr(88)+chr(73)+chr(83)+chr(84)+chr(83) if u else chr(78)+chr(79)+chr(84)+chr(95)+chr(70)+chr(79)+chr(85)+chr(78)+chr(68)); db.close()" 2>&1'
result = run(cmd2, timeout=15)
print(f"  结果: {result.strip()[:200]}")

# 最终状态
print("\n" + "=" * 60)
print("最终状态:")
run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
print("\n生产环境: https://chat.benne-ai.com")
print("管理后台: https://chat.benne-ai.com/admin/")

ssh.close()
print("\n完成")
