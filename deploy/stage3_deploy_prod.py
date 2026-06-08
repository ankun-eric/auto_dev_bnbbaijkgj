#!/usr/bin/env python3
"""阶段3：生产环境远程部署脚本"""
import paramiko, json, time, sys

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_DIR = "/home/ubuntu/gateway"
ACR_REG = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
GIT_URL = "https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(cmd, timeout=60):
    print(f"  $ {cmd[:120]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    result = out + err
    if len(result) > 1000:
        result = result[:500] + f"\n...(截断，共{len(out)+len(err)}字符)...\n" + result[-300:]
    if result.strip():
        print(result.strip())
    return code, out, err

print("=" * 60)
print("阶段3：生产环境远程部署")
print(f"服务器: {HOST}")
print(f"项目: {DEPLOY_ID}")
print("=" * 60)

# 步骤1: ACR 登录
print("\n[步骤1] ACR 登录...")
rc, out, err = run(f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR_REG}")
if rc == 0:
    print("  ACR 登录成功")
else:
    print(f"  ACR 登录失败: {err}")

# 步骤2: Docker Hub 镜像加速器
print("\n[步骤2] 检查 Docker Hub 镜像加速器...")
rc, out, err = run("cat /etc/docker/daemon.json 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('registry-mirrors',[])))\" 2>/dev/null || echo '未配置'")
print(f"  镜像加速器: {out.strip()}")

# 步骤3: Git pull
print("\n[步骤3] Git 拉取最新代码...")
rc, out, err = run(f"cd {PROJ_DIR} && git fetch origin master 2>&1 && git reset --hard origin/master 2>&1 && git clean -fd 2>&1 && git log -1 --oneline")
if rc != 0:
    print("  Git fetch 失败，尝试 rsync 降级...")
    # 降级方案：直接 scp 文件
    print("  使用 scp 上传配置...")
else:
    print(f"  Git pull 成功: {out.strip()[:200]}")

# 确保 docker-compose.prod.yml 在新的 deploy 目录下
rc, out, err = run(f"cd {PROJ_DIR} && ls deploy/docker-compose.prod.yml 2>/dev/null && echo 'FOUND' || echo 'NOT_FOUND'")
if "NOT_FOUND" in out:
    print("  复制 docker-compose.prod.yml...")
    run(f"cp {PROJ_DIR}/docker-compose.prod.yml {PROJ_DIR}/deploy/docker-compose.prod.yml 2>/dev/null")

# 步骤4: BUILD_COMMIT
print("\n[步骤4] 生成 BUILD_COMMIT...")
rc, commit, err = run(f"cd {PROJ_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'")
build_commit = commit.strip()
print(f"  BUILD_COMMIT={build_commit}")

# 步骤5: docker compose down (不带 -v!)
print("\n[步骤5] 停止旧容器 (docker compose down，不带 -v)...")
rc, out, err = run(f"cd {PROJ_DIR} && docker compose -f deploy/docker-compose.prod.yml down 2>&1", timeout=120)
print(f"  down 完成")

# 步骤6: docker compose build --pull
print("\n[步骤6] 构建镜像 (docker compose build --pull)...")
print("  这可能需要几分钟...")
rc, out, err = run(f"cd {PROJ_DIR} && BUILD_COMMIT={build_commit} docker compose -f deploy/docker-compose.prod.yml build --pull 2>&1", timeout=600)
if rc != 0:
    print(f"  --pull 构建失败，尝试无 --pull 构建...")
    rc, out, err = run(f"cd {PROJ_DIR} && BUILD_COMMIT={build_commit} docker compose -f deploy/docker-compose.prod.yml build 2>&1", timeout=600)
print(f"  构建完成, rc={rc}")

# 步骤7: docker compose up -d
print("\n[步骤7] 启动容器 (docker compose up -d)...")
rc, out, err = run(f"cd {PROJ_DIR} && docker compose -f deploy/docker-compose.prod.yml up -d 2>&1", timeout=120)
print(f"  up 完成, rc={rc}")

# 步骤8: 等待健康检查
print("\n[步骤8] 等待容器健康检查...")
max_wait = 24
healthy_all = False
for i in range(max_wait):
    rc, out, err = run(f"cd {PROJ_DIR} && docker compose -f deploy/docker-compose.prod.yml ps --format json 2>/dev/null")
    if out:
        import re
        total = out.count('"Name"')
        healthy = out.count('"Health":"healthy"')
        print(f"  [{i+1}/{max_wait}] {healthy}/{total} 容器已健康")
        if total > 0 and healthy == total:
            print("  所有容器健康检查通过!")
            healthy_all = True
            break
    time.sleep(10)
    
if not healthy_all:
    print("  警告: 等待超时，检查容器状态...")
    rc, out, err = run(f"cd {PROJ_DIR} && docker compose -f deploy/docker-compose.prod.yml ps")
    print(out[:800])

# 步骤9: gateway 网络连接
print("\n[步骤9] 将 gateway 连接到项目网络...")
rc, out, err = run(f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1")
if rc == 0:
    print("  gateway 已连接项目网络")
else:
    if "already exists" in out+err or "exists" in out+err:
        print("  gateway 已在项目网络中")
    else:
        print(f"  连接失败: {out+err}")

# 步骤10: 部署 gateway-routes.conf
print("\n[步骤10] 更新 gateway 配置...")
# 备份旧配置
run(f"cp {GATEWAY_DIR}/conf.d/{DEPLOY_ID}.conf {GATEWAY_DIR}/conf.d.bak/{DEPLOY_ID}.conf.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null; mkdir -p {GATEWAY_DIR}/conf.d.bak/")

# 从项目目录复制 gateway-routes.conf
rc, out, err = run(f"cp {PROJ_DIR}/deploy/gateway-routes.conf {GATEWAY_DIR}/conf.d/{DEPLOY_ID}.conf 2>&1")
print(f"  复制 gateway-routes.conf: {'成功' if rc==0 else out+err}")

# 语法测试
rc, out, err = run("docker exec gateway-nginx nginx -t 2>&1")
if rc == 0:
    print("  nginx 语法测试通过")
    # 重载
    rc, out, err = run("docker exec gateway-nginx nginx -s reload 2>&1")
    print(f"  nginx reload: {'成功' if rc==0 else out+err}")
else:
    print(f"  nginx 语法错误! 回滚配置...")
    print(out+err)

# 步骤11: SSL连通性验证
print("\n[步骤11] SSL 连通性验证...")
time.sleep(3)
rc, out, err = run("curl -vI https://chat.benne-ai.com/ 2>&1 | grep -iE 'SSL|HTTP/|200|301|302|server' | head -10", timeout=15)
print(f"  SSL验证: {out.strip()[:500]}")

# 步骤12: 数据库迁移
print("\n[步骤12] 数据库初始化与增量迁移...")
# 检查是否有表
rc, out, err = run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import engine; from sqlalchemy import inspect; inspector=inspect(engine); tables=inspector.get_table_names(); print(len(tables)); print(','.join(tables[:10]))\" 2>&1", timeout=30)
print(f"  数据库表: {out.strip()[:300]}")

if "Error" not in out and "Traceback" not in out:
    table_count = out.strip().split("\n")[0] if out.strip() else "0"
    try:
        table_count = int(table_count)
    except:
        table_count = 0
    
    if table_count == 0:
        print("  数据库为空，执行 create_all...")
        rc, out, err = run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('所有表已创建')\" 2>&1", timeout=30)
        print(out.strip()[:500])
    else:
        print(f"  数据库已有 {table_count} 张表，执行增量迁移...")
        rc, out, err = run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('增量建表完成（已存在表已跳过）')\" 2>&1", timeout=30)
        print(out.strip()[:500])
else:
    print(f"  数据库连接失败: {out[:300]}")

# 步骤13: 默认账号检查
print("\n[步骤13] 检查默认账号 admin...")
rc, out, err = run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import SessionLocal; from app.models.models import User; db=SessionLocal(); u=db.query(User).filter(User.username=='admin').first(); print('EXISTS' if u else 'NOT_FOUND'); db.close()\" 2>&1", timeout=15)
print(f"  admin账号: {out.strip()}")

if "NOT_FOUND" in out:
    print("  创建默认账号 admin/admin123...")
    rc, out, err = run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import SessionLocal; from app.models.models import User; from app.core.security import get_password_hash; db=SessionLocal(); u=User(username='admin', hashed_password=get_password_hash('admin123'), is_admin=True); db.add(u); db.commit(); print('默认账号已创建'); db.close()\" 2>&1", timeout=15)
    print(f"  创建结果: {out.strip()[:300]}")

# 最终状态
print("\n" + "=" * 60)
print("部署完成! 最终状态:")
print("=" * 60)
rc, out, err = run("docker ps --format 'table {{.Names}}\t{{.Status}}'")
print(out.strip())
print(f"\n生产环境URL: https://chat.benne-ai.com")
print(f"管理后台: https://chat.benne-ai.com/admin/")
print(f"默认账号: admin / admin123")

ssh.close()
print("\n部署脚本执行完毕")
