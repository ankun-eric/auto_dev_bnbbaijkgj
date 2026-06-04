#!/usr/bin/env python3
"""在 backend 容器内安装测试依赖并运行睡眠测试（容器已含 runtime 依赖）。
前端静态断言会 skip（容器无前端源码），前端断言改在本地 Windows 运行。"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd, PROJECT_DIR

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BE = f'{DEPLOY_ID}-backend'
SRC = f'{PROJECT_DIR}/backend'

ssh = get_ssh()
# 拷贝 tests 目录进容器
run_cmd(ssh, f'docker cp {SRC}/tests {BE}:/app/tests 2>&1; echo cp_done', 60)
# 安装测试依赖
run_cmd(ssh, f'docker exec {BE} pip install -q pytest pytest-asyncio aiosqlite 2>&1 | tail -8', 300)
# 跑测试
run_cmd(ssh, f'docker exec -w /app {BE} python -m pytest tests/test_sleep_align_bp_v1_20260602.py -v 2>&1 | tail -55', 600)
ssh.close()
