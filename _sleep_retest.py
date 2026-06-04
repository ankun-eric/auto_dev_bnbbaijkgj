#!/usr/bin/env python3
"""上传更新后的测试文件到容器并重跑全部睡眠测试"""
import sys
sys.path.insert(0, 'deploy')
import paramiko
from ssh_helper import HOST, USER, PASSWORD, get_ssh, run_cmd, PROJECT_DIR

BE = '6b099ed3-7175-4a78-91f4-44570c84ed27-backend'
LOCAL = r'backend/tests/test_sleep_align_bp_v1_20260602.py'
REMOTE_TMP = '/home/ubuntu/test_sleep_align_bp_v1_20260602.py'

ssh = get_ssh()
# sftp 上传到 host
sftp = ssh.open_sftp()
sftp.put(LOCAL, REMOTE_TMP)
sftp.close()
# copy 到 host repo + 容器
run_cmd(ssh, f'cp {REMOTE_TMP} {PROJECT_DIR}/backend/tests/test_sleep_align_bp_v1_20260602.py; echo host_ok', 30)
run_cmd(ssh, f'docker cp {REMOTE_TMP} {BE}:/app/tests/test_sleep_align_bp_v1_20260602.py; echo ctr_ok', 30)
# 重跑
run_cmd(ssh, f'docker exec -w /app {BE} python -m pytest tests/test_sleep_align_bp_v1_20260602.py -v -p no:warnings --tb=short 2>&1 | grep -vE "Deprecat|warn|UserWarning|model_|orm_mode|regex|pydantic|fastapi" | tail -45', 600)
ssh.close()
