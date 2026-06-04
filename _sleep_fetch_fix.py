#!/usr/bin/env python3
"""强制拉取 origin/master 到服务器（处理 shallow clone）"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR
ssh = get_ssh()
run_cmd(ssh, f'cd {PROJECT_DIR} && git rev-parse --is-shallow-repository 2>&1', 30)
run_cmd(ssh, f'cd {PROJECT_DIR} && git fetch origin master 2>&1 | tail -5', 180)
run_cmd(ssh, f'cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 | tail -3', 60)
run_cmd(ssh, f'cd {PROJECT_DIR} && git log -1 --oneline 2>&1', 30)
run_cmd(ssh, f'ls -la {PROJECT_DIR}/backend/tests/test_sleep_align_bp_v1_20260602.py 2>&1', 30)
run_cmd(ssh, f'ls -la {PROJECT_DIR}/h5-web/src/lib/sleep-level.ts 2>&1', 30)
ssh.close()
