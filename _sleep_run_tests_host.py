#!/usr/bin/env python3
"""在服务器 host 上用 venv 跑睡眠对齐测试（sqlite 内存库，含前端静态断言）"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR

ssh = get_ssh()
BE = f'{PROJECT_DIR}/backend'
VENV = '/home/ubuntu/.venv_sleep_test'

# 创建/复用 venv
run_cmd(ssh, f'test -d {VENV} || python3 -m venv {VENV} 2>&1; echo venv_ok', 120)
# 安装依赖（test + runtime）
run_cmd(ssh, f'{VENV}/bin/pip install -q -r {BE}/requirements.txt -r {BE}/requirements-test.txt 2>&1 | tail -8', 600)
# 跑测试
run_cmd(ssh, f'cd {BE} && {VENV}/bin/python -m pytest tests/test_sleep_align_bp_v1_20260602.py -v 2>&1 | tail -50', 600)
ssh.close()
