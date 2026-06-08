#!/usr/bin/env python3
"""修复生产环境部署"""
import paramiko, time, re

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "chat.benne-ai.com"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GW_DIR = "/home/ubuntu/gateway"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username="ubuntu", password="Benne-ai@#", timeout=30)

def run(cmd, timeout=60):
    print(f"  > {cmd[:150]}")
    _, o, e = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    result = out + err
    # 清理 ANSI 转义序列
    result = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', result)
    result = re.sub(r'\x1b\[[?]\d+[hl]', '', result)
    result = re.sub(r'\x1b\[[=]', '', result)
    if len(result) > 600:
        result = result[:300] + "\n...(截断)...\n" + result[-200:]
    if result.strip():
        print(result.strip())
    return out + err

print("=" * 60)
print("修复生产环境部署")
print("=" * 60)

# 1. Git pull 最新代码
print("\n[1] Git pull 最新代码...")
run(f"cd {PROJ_DIR} && git fetch origin master 2>&1 && git reset --hard origin/master 2>&1 && echo GIT_PULL_OK", timeout=60)

# 2. 获取干净的 BUILD_COMMIT
print("\n[2] 获取 BUILD_COMMIT...")
raw, _, _ = ssh.exec_command(f"cd {PROJ_DIR} && git rev-parse HEAD", timeout=15)
# 通过 stderr 读取 STDOUT 避免 ANSI
chan = ssh.get_transport().open_session()
chan.exec_command(f"cd {PROJ_DIR} && git rev-parse HEAD")
commit_raw = chan.recv(1024).decode().strip()
chan.close()
# 取第一行非空行
for line in commit_raw.split('\n'):
    line = line.strip()
    if len(line) == 40 and all(c in '0123456789abcdef' for c in line):
        BUILD_COMMIT = line
        break
else:
    BUILD_COMMIT = "unknown"
print(f"  BUILD_COMMIT = {BUILD_COMMIT}")

# 3. 停止旧容器
print("\n[3] 停止旧容器...")
run("docker stop 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 6b099ed3-7175-4a78-91f4-44570c84ed27-admin 2>/dev/null; docker rm 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 6b099ed3-7175-4a78-91f4-44570c84ed27-admin 2>/dev/null; echo 'DONE'", timeout=120)
print("  旧容器已停止和删除")

# 4. 构建镜像
print("\n[4] 构建 Docker 镜像...")
build_cmd = f"cd {PROJ_DIR} && BUILD_COMMIT={BUILD_COMMIT} docker compose -f deploy/docker-compose.prod.yml build --pull 2>&1"
run(build_cmd, timeout=900)
print("  构建完成")

# 5. 启动容器
print("\n[5] 启动容器...")
run(f"cd {PROJ_DIR} && docker compose -f deploy/docker-compose.prod.yml up -d 2>&1", timeout=120)
print("  容器启动命令已执行")

# 6. 等待健康检查
print("\n[6] 等待健康检查...")
for i in range(24):
    time.sleep(10)
    result = run(f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'", timeout=10)
    if "healthy" in result:
        lines = result.strip().split('\n')
        healthy = sum(1 for l in lines if 'healthy' in l)
        total = len([l for l in lines if l.strip()])
        print(f"  [{i+1}/24] {healthy}/{total} healthy")
        if total >= 3 and healthy == total:
            print("  所有容器健康!")
            break
    else:
        print(f"  [{i+1}/24] 等待中...")
else:
    print("  警告: 等待超时")

# 7. 更新 gateway 配置
print("\n[7] 更新 gateway 配置...")
# 备份
run(f"sudo cp {GW_DIR}/conf.d/{DEPLOY_ID}.conf {GW_DIR}/conf.d.bak/{DEPLOY_ID}.conf.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null; sudo mkdir -p {GW_DIR}/conf.d.bak/; echo backup_done")
# 复制新配置
run(f"sudo cp {PROJ_DIR}/deploy/gateway-routes.conf {GW_DIR}/conf.d/{DEPLOY_ID}.conf && echo copy_ok || echo copy_failed")
# 语法测试
result = run("docker exec gateway-nginx nginx -t 2>&1")
if "successful" in result:
    print("  nginx 语法通过")
    run("docker exec gateway-nginx nginx -s reload 2>&1")
    print("  nginx 已重载")
else:
    print(f"  nginx 语法错误: {result[:300]}")

# 8. gateway 网络连接确认
print("\n[8] 确认 gateway 网络连接...")
run(f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || echo 'already_connected'")

# 9. SSL 验证
print("\n[9] SSL 验证...")
time.sleep(3)
run("curl -sI https://chat.benne-ai.com/ 2>&1 | head -5")

# 10. 数据库迁移
print("\n[10] 数据库迁移...")
run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('DB_MIGRATE_OK')\" 2>&1", timeout=30)

# 11. 默认账号
print("\n[11] 检查默认账号...")
run(f"docker exec {DEPLOY_ID}-backend python -c \"from app.database import SessionLocal; from app.models.models import User; db=SessionLocal(); u=db.query(User).filter(User.username=='admin').first(); print('ADMIN_EXISTS' if u else 'ADMIN_NOT_FOUND'); db.close()\" 2>&1", timeout=15)

# 最终状态
print("\n" + "=" * 60)
print("最终状态:")
run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
print("\n生产环境: https://chat.benne-ai.com")
print("管理后台: https://chat.benne-ai.com/admin/")

ssh.close()
print("\n部署完成")
