#!/usr/bin/env python3
"""[PRD-SLEEP-ALIGN-BP-V1] 部署前状态探查"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR

ssh = get_ssh()
cmds = [
    'docker ps --filter name=6b099ed3 --format "{{.Names}}\\t{{.Status}}"',
    f'cd {PROJECT_DIR} && git log -1 --oneline 2>&1',
    f'cd {PROJECT_DIR} && git remote -v 2>&1 | head -2',
    f'cd {PROJECT_DIR} && ls docker-compose*.yml 2>&1',
    'docker ps --filter name=gateway --format "{{.Names}}" 2>&1',
    'ls /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>&1',
]
for c in cmds:
    run_cmd(ssh, c, timeout=60)
ssh.close()
