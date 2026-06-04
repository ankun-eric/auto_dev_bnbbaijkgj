#!/usr/bin/env python3
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd
BE = '6b099ed3-7175-4a78-91f4-44570c84ed27-backend'
ssh = get_ssh()
run_cmd(ssh, f'docker exec -w /app {BE} python -m pytest tests/test_sleep_align_bp_v1_20260602.py::test_sleep_metric_crud -v -p no:warnings --tb=short 2>&1 | grep -vE "Deprecat|warn|UserWarning|model_|orm_mode|regex|pydantic|fastapi|^\\s*$" | tail -40', 300)
ssh.close()
