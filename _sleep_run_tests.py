#!/usr/bin/env python3
"""[PRD-SLEEP-ALIGN-BP-V1] 在 backend 容器内跑睡眠对齐测试"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BE = f'{DEPLOY_ID}-backend'

ssh = get_ssh()
# 确认测试文件已进容器
run_cmd(ssh, f'docker exec {BE} ls -la tests/test_sleep_align_bp_v1_20260602.py 2>&1', timeout=30)
# 运行测试
run_cmd(ssh, f'docker exec {BE} python -m pytest tests/test_sleep_align_bp_v1_20260602.py -v 2>&1 | tail -60', timeout=300)
ssh.close()
