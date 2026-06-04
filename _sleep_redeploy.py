#!/usr/bin/env python3
"""重建 backend + h5（新代码已 reset 到 03e08be）"""
import sys, time
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
GW = 'gateway-nginx'

ssh = get_ssh()
run_cmd(ssh, f'cd {PROJECT_DIR} && git log -1 --oneline', 30)
print("=== building backend + h5-web (no-cache) ===")
run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web 2>&1 | tail -25', 1500)
run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1 | tail -12', 300)
run_cmd(ssh, f'docker network connect {DEPLOY_ID}-network {GW} 2>/dev/null; echo done', 30)
time.sleep(8)
run_cmd(ssh, f'docker ps --filter name={DEPLOY_ID} --format "{{{{.Names}}}}\\t{{{{.Status}}}}"', 30)
run_cmd(ssh, f'docker exec {GW} nginx -s reload 2>&1; echo reloaded', 30)
ssh.close()
print("=== redeploy finished ===")
