#!/usr/bin/env python3
"""[PRD-SLEEP-ALIGN-BP-V1] 部署：git pull + rebuild h5/backend(--no-cache) + 重启 + 重连网关网络"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
GW = 'gateway-nginx'

ssh = get_ssh()

# 1. 拉取最新代码
run_cmd(ssh, f'cd {PROJECT_DIR} && git fetch origin --depth 1 --no-tags 2>&1 | tail -3', timeout=120)
run_cmd(ssh, f'cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 | tail -3', timeout=60)
run_cmd(ssh, f'cd {PROJECT_DIR} && git log -1 --oneline', timeout=30)

# 2. BUILD_COMMIT
run_cmd(ssh, f'cd {PROJECT_DIR} && echo "BUILD_COMMIT=$(git log -1 --format=%H)" ', timeout=30)

# 3. 重建 h5 + backend（仅改动端），无缓存
print("=== building backend + h5-web (no-cache) ===")
run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web 2>&1 | tail -30', timeout=1500)

# 4. 重启容器
run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1 | tail -15', timeout=300)

# 5. 重新连接 gateway 到项目网络（防 502）
run_cmd(ssh, f'docker network connect {DEPLOY_ID}-network {GW} 2>/dev/null; echo done', timeout=30)

# 6. 等待容器就绪
import time
time.sleep(8)
run_cmd(ssh, f'docker ps --filter name={DEPLOY_ID} --format "{{{{.Names}}}}\\t{{{{.Status}}}}"', timeout=30)

# 7. reload gateway
run_cmd(ssh, f'docker exec {GW} nginx -t 2>&1', timeout=30)
run_cmd(ssh, f'docker exec {GW} nginx -s reload 2>&1; echo reloaded', timeout=30)

ssh.close()
print("=== deploy script finished ===")
