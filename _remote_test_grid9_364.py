#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[364] 服务器内运行 pytest 验证"""
import paramiko, time, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD,
            timeout=30, look_for_keys=False, allow_agent=False)

# pytest 在容器内执行
print("=== install pytest in backend container if missing ===", flush=True)
cmd = f"docker exec {DEPLOY_ID}-backend pip install -q pytest pytest-asyncio 2>&1 | tail -5"
_, stdout, _ = cli.exec_command(cmd, timeout=300)
print(stdout.read().decode(errors='replace'), flush=True)

print("\n=== run pytest test_merchant_dashboard_v1 + grid9 ===", flush=True)
cmd = (f"docker exec {DEPLOY_ID}-backend bash -c "
       f"'cd /app && python -m pytest tests/test_merchant_dashboard_v1.py tests/test_merchant_dashboard_grid9.py -v 2>&1' | tail -80")
_, stdout, _ = cli.exec_command(cmd, timeout=300)
out = stdout.read().decode(errors='replace')
print(out, flush=True)

# 用接口实际测一下
import urllib.request, json
print("\n=== smoke API time-slots ===", flush=True)
url = f"https://{HOST}/autodev/{DEPLOY_ID}/api/merchant/dashboard/time-slots"
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())
    print(f"  slots count = {len(data.get('slots', []))}", flush=True)
    assert len(data.get('slots', [])) == 9
    print("  ✓ 9 slots OK", flush=True)
except Exception as e:
    print(f"  ! {e}", flush=True)

cli.close()
