#!/usr/bin/env python3
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR
ssh = get_ssh()
run_cmd(ssh, f'ls {PROJECT_DIR}/backend/tests/conftest.py 2>&1', 30)
run_cmd(ssh, f'ls {PROJECT_DIR}/backend/tests/test_sleep_align_bp_v1_20260602.py 2>&1', 30)
run_cmd(ssh, 'which python3; python3 --version 2>&1', 30)
run_cmd(ssh, f'cat {PROJECT_DIR}/backend/tests/conftest.py 2>&1 | head -60', 30)
run_cmd(ssh, f'ls {PROJECT_DIR}/backend/*.txt {PROJECT_DIR}/backend/requirements*.txt 2>&1', 30)
ssh.close()
