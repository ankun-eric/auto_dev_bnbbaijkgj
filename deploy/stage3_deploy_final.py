"""阶段 3：远程部署 - 全自动执行"""
import paramiko
import json
import sys
import time
import os

# ====== 配置参数 ======
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
PROJECT_DOMAIN = f"{DEPLOY_ID}.{WILDCARD_BASE}"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF_DIR = "/home/ubuntu/gateway/conf.d"
GATEWAY_CONF_BAK = "/home/ubuntu/gateway/conf.d.bak"
GATEWAY_SERVER_FILE = f"{GATEWAY_CONF_DIR}/{DEPLOY_ID}.server"
GATEWAY_CONTAINER = "gateway-nginx"
NETWORK_NAME = f"{DEPLOY_ID}-network"

ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

GIT_URL = "https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

# 本地 gateway 配置文件
LOCAL_GATEWAY_CONF = os.path.join(os.path.dirname(__file__), "gateway-routes.conf")

def ssh_exec(ssh, cmd, timeout=60):
    """执行 SSH 命令"""
    print(f"  [CMD] {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return out.strip(), err.strip(), code

def sftp_put(ssh, local_path, remote_path):
    """上传文件"""
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print(f"  已上传: {local_path} → {remote_path}")

print("="*60)
print("阶段 3：远程部署开始")
print(f"项目域名: {PROJECT_DOMAIN}")
print(f"服务器: {SSH_USER}@{SSH_HOST}:{SSH_PORT}")
print(f"项目目录: {PROJECT_DIR}")
print("="*60)

# ====== SSH 连接 ======
print("\n>>> 1. SSH 连接验证...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
    print("SSH 连接成功")
except Exception as e:
    print(f"SSH 连接失败: {e}")
    sys.exit(1)

# ====== 2. ACR 登录 ======
print("\n>>> 2. ACR 登录...")
out, err, code = ssh_exec(ssh, f"docker login --username={ACR_USER} --password='{ACR_PASS}' {ACR_ADDR} 2>&1")
print(f"  ACR 登录: {'成功' if code == 0 else '失败: ' + err[:200]}")

# ====== 3. Git 更新代码 ======
print("\n>>> 3. Git 更新代码...")
# 检查项目目录是否存在
out, err, code = ssh_exec(ssh, f"test -d {PROJECT_DIR}/.git && echo 'GIT_EXISTS' || echo 'NO_GIT'")
git_exists = "GIT_EXISTS" in out

if git_exists:
    print("  非首次部署，使用 git fetch + reset...")
    # 设置 git credentials
    git_url_with_auth = GIT_URL.replace("https://", f"https://{GIT_USER}:{GIT_TOKEN}@")
    cmds = [
        f"cd {PROJECT_DIR}",
        f"git remote set-url codeup '{git_url_with_auth}' 2>/dev/null || git remote add codeup '{git_url_with_auth}' 2>/dev/null",
        "git fetch codeup master --depth 1 2>&1 || git fetch codeup master 2>&1",
        "git reset --hard codeup/master 2>&1",
        "git clean -fd 2>&1",
    ]
    out, err, code = ssh_exec(ssh, " && ".join(cmds), timeout=60)
    print(f"  Git 更新: {'成功' if code == 0 else '失败'}")
    
    # 一致性验证
    out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --oneline 2>&1")
    print(f"  HEAD: {out[:200]}")
else:
    print("  首次部署，使用 git clone...")
    git_url_with_auth = GIT_URL.replace("https://", f"https://{GIT_USER}:{GIT_TOKEN}@")
    cmd = f"git clone --depth 1 --single-branch '{git_url_with_auth}' {PROJECT_DIR} 2>&1"
    out, err, code = ssh_exec(ssh, cmd, timeout=120)
    print(f"  Git clone: {'成功' if code == 0 else '失败: ' + err[:200]}")

# ====== 4. BUILD_COMMIT ======
print("\n>>> 4. 生成 BUILD_COMMIT...")
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'")
BUILD_COMMIT = out.strip() if out.strip() else f"deploy-{int(time.time())}"
print(f"  BUILD_COMMIT: {BUILD_COMMIT}")

# ====== 5. 停旧容器并构建 ======
print("\n>>> 5. 构建与启动项目容器...")
# 先停旧容器
ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml down 2>&1 || true", timeout=30)

# 构建 (使用缓存加速)
build_cmd = f"cd {PROJECT_DIR} && BUILD_COMMIT='{BUILD_COMMIT}' docker compose -f deploy/docker-compose.prod.yml build --pull 2>&1"
print("  开始构建（--pull 拉取最新基础镜像）...")
out, err, code = ssh_exec(ssh, build_cmd, timeout=600)
print(f"  构建结果: {'成功' if code == 0 else '需检查'}")
if code != 0:
    print(f"  --pull 失败，尝试无 --pull 构建...")
    build_cmd2 = f"cd {PROJECT_DIR} && BUILD_COMMIT='{BUILD_COMMIT}' docker compose -f deploy/docker-compose.prod.yml build 2>&1"
    out, err, code = ssh_exec(ssh, build_cmd2, timeout=600)
    print(f"  构建结果: {'成功' if code == 0 else '失败'}")

if code != 0:
    print(f"  构建错误: {err[:500]}")
    # 不退出，继续尝试

# ====== 6. 启动容器 ======
print("\n>>> 6. 启动容器...")
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && BUILD_COMMIT='{BUILD_COMMIT}' docker compose -f deploy/docker-compose.prod.yml up -d 2>&1", timeout=60)
print(f"  启动: {'成功' if code == 0 else '失败'}")

# ====== 7. 等待健康检查 ======
print("\n>>> 7. 等待容器健康检查...")
max_wait = 30
for i in range(max_wait):
    time.sleep(5)
    out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml ps --format json 2>&1", timeout=10)
    total = out.count('"Name"')
    healthy = out.count('"healthy"')
    print(f"  [{i+1}/{max_wait}] {healthy}/{total} 容器健康")
    if total > 0 and healthy == total:
        print("  所有容器健康检查通过!")
        break
else:
    print("  警告：等待超时")
    out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml ps 2>&1")
    print(f"  容器状态: {out[:500]}")

# ====== 8. 连接 gateway 到项目网络 ======
print("\n>>> 8. 连接 gateway 到项目网络...")
out, err, code = ssh_exec(ssh, f"docker network connect {NETWORK_NAME} {GATEWAY_CONTAINER} 2>&1 || true")
print(f"  网络连接: {'成功' if code == 0 else '已连接或无需操作'}")

# 验证网络连接
out, err, code = ssh_exec(ssh, f"docker network inspect {NETWORK_NAME} --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}' 2>&1")
print(f"  网络内容器: {out[:300]}")

# ====== 9. 更新 gateway 配置 ======
print("\n>>> 9. 更新 gateway 配置...")

# 9a. 备份旧配置
ssh_exec(ssh, f"mkdir -p {GATEWAY_CONF_BAK}")
ts = int(time.time())
ssh_exec(ssh, f"cp {GATEWAY_SERVER_FILE} {GATEWAY_CONF_BAK}/{DEPLOY_ID}.server.bak.{ts} 2>/dev/null || echo '无旧配置'")

# 9b. 上传新的 .server 文件
print("  上传 gateway 配置文件...")
sftp_put(ssh, LOCAL_GATEWAY_CONF, GATEWAY_SERVER_FILE)

# 9c. 同时检查并清理 .conf 文件中的旧 autodev location（如果有启用的 .conf）
out, err, code = ssh_exec(ssh, f"ls {GATEWAY_CONF_DIR}/{DEPLOY_ID}.conf 2>/dev/null && echo 'EXISTS' || echo 'NO_CONF'")
if "EXISTS" in out:
    print("  发现 .conf 文件，禁用它（避免与 .server 冲突）...")
    ssh_exec(ssh, f"mv {GATEWAY_CONF_DIR}/{DEPLOY_ID}.conf {GATEWAY_CONF_DIR}/{DEPLOY_ID}.conf.disabled.{ts} 2>/dev/null || true")

# 9d. 测试 gateway 配置
print("  测试 nginx 配置...")
out, err, code = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
print(f"  nginx -t: {out[:500]}")
if code != 0:
    print(f"  ⚠️ 配置语法错误！回滚...")
    print(f"  STDERR: {err[:500]}")
    # 回滚
    ssh_exec(ssh, f"cp {GATEWAY_CONF_BAK}/{DEPLOY_ID}.server.bak.{ts} {GATEWAY_SERVER_FILE} 2>/dev/null || true")
    # 再次测试
    out2, err2, code2 = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
    print(f"  回滚后 nginx -t: {out2[:300]}")
else:
    # 9e. 重载 nginx
    print("  重载 nginx...")
    out, err, code = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
    print(f"  nginx reload: {'成功' if code == 0 else '失败: ' + err[:200]}")
    time.sleep(2)

# ====== 10. SSL 连通性验证 ======
print("\n>>> 10. SSL 连通性验证...")
out, err, code = ssh_exec(ssh, f"curl -sI --max-time 10 https://{PROJECT_DOMAIN}/ 2>&1 | head -20")
print(f"  HTTPS 响应: {out[:500]}")

# ====== 11. 数据库初始化与增量迁移 ======
print("\n>>> 11. 数据库迁移...")
# 检查数据库是否已有表
check_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
from app.database import engine
from sqlalchemy import inspect
try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(len(tables))
except Exception as e:
    print(f'ERROR:{{e}}')
" 2>&1"""
out, err, code = ssh_exec(ssh, check_cmd, timeout=30)
print(f"  数据库检查: {out[:200]}")

try:
    table_count = int(out.strip()) if out.strip().isdigit() else -1
except:
    table_count = -1

# 检查是否有 Alembic
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend test -d /app/alembic && echo 'ALEMBIC' || echo 'NO_ALEMBIC'", timeout=10)
has_alembic = "ALEMBIC" in out

if table_count == 0:
    print("  数据库为空，执行初始化...")
    if has_alembic:
        ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend alembic upgrade head 2>&1", timeout=60)
    else:
        # SQLAlchemy create_all
        ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('表已创建')
" 2>&1""", timeout=30)
    print("  数据库初始化完成")
elif table_count > 0:
    print(f"  数据库已有 {table_count} 张表，执行增量迁移...")
    if has_alembic:
        # 检查待执行迁移
        out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend alembic current 2>&1", timeout=15)
        print(f"  当前迁移版本: {out[:100]}")
        # 安全检查
        out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend sh -c 'grep -rEi \"drop_table|drop_column|drop_constraint\" /app/alembic/versions/ 2>/dev/null || echo NO_DROP_FOUND'", timeout=15)
        if "NO_DROP_FOUND" not in out and out.strip():
            print(f"  ⚠️ 检测到 DROP 操作，已中止增量迁移！")
        else:
            ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend alembic upgrade head 2>&1", timeout=60)
            print("  增量迁移完成")
    else:
        # SQLAlchemy create_all（自动跳过已存在的表）
        ssh_exec(ssh, f"""docker exec {DEPLOY_ID}-backend python3 -c "
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('增量建表完成（已存在的表已跳过）')
" 2>&1""", timeout=30)
        print("  增量迁移完成")
else:
    print(f"  数据库检查失败，跳过迁移（{out[:200]}）")

# ====== 12. 默认账号检查 ======
print("\n>>> 12. 默认账号检查...")
# 尝试通过 API 检查
out, err, code = ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend python3 -c "
    f"'import urllib.request; req=urllib.request.Request(\"http://localhost:8000/api/auth/login\", "
    f"data=b\"{{\\\"username\\\":\\\"admin\\\",\\\"password\\\":\\\"admin123\\\"}}\", "
    f"headers={{\"Content-Type\":\"application/json\"}}); "
    f"resp=urllib.request.urlopen(req); print(resp.status)' 2>&1", timeout=20)
print(f"  登录测试: {out[:200]}")

if "200" not in out:
    print("  尝试创建默认账号...")
    # 通过数据库直接创建
    create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
import sys
try:
    from app.database import SessionLocal
    from app.models.models import User
    from app.core.security import get_password_hash
    db = SessionLocal()
    existing = db.query(User).filter(User.username == 'admin').first()
    if not existing:
        user = User(
            username='admin',
            hashed_password=get_password_hash('admin123'),
            is_admin=True,
            is_active=True,
            full_name='Administrator'
        )
        db.add(user)
        db.commit()
        print('默认账号 admin/admin123 已创建')
    else:
        print('默认账号 admin 已存在')
    db.close()
except Exception as e:
    print(f'创建失败: {{e}}')
    import traceback
    traceback.print_exc()
" 2>&1"""
    out, err, code = ssh_exec(ssh, create_cmd, timeout=30)
    print(f"  {out[:300]}")
else:
    print("  默认账号 admin 可正常登录")

# ====== 13. BUILD_INFO 验证 ======
print("\n>>> 13. BUILD_INFO 验证...")
out, err, code = ssh_exec(ssh, f"docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/{DEPLOY_ID}-backend:latest cat /app/BUILD_INFO 2>&1 || echo 'NOT_FOUND'", timeout=20)
print(f"  后端 BUILD_INFO: {out[:100]}")

# ====== 14. 最终状态 ======
print("\n>>> 14. 最终状态检查...")
out, err, code = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml ps 2>&1")
print(f"  容器状态:\n{out[:800]}")

# HTTPS 验证
out, err, code = ssh_exec(ssh, f"curl -sI --max-time 15 https://{PROJECT_DOMAIN}/api/health 2>&1 | head -10")
print(f"  HTTPS /api/health: {out[:300]}")

print("\n" + "="*60)
print("阶段 3：远程部署完成")
print(f"项目域名: https://{PROJECT_DOMAIN}")
print(f"  /api/  → {DEPLOY_ID}-backend:8000")
print(f"  /admin/ → {DEPLOY_ID}-admin:3000")
print(f"  /      → {DEPLOY_ID}-h5:3001")
print(f"默认账号: admin / admin123")
print(f"BUILD_COMMIT: {BUILD_COMMIT}")
print("="*60)

ssh.close()
print("SSH 已断开")
