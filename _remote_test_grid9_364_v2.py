#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[364] 服务器内运行 pytest 验证 v2 - 装 aiosqlite + 跑测试"""
import paramiko, time, sys, urllib.request, json

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD,
            timeout=30, look_for_keys=False, allow_agent=False)

print("=== install aiosqlite in backend ===", flush=True)
cmd = f"docker exec {DEPLOY_ID}-backend pip install -q aiosqlite httpx 2>&1 | tail -3"
_, stdout, _ = cli.exec_command(cmd, timeout=300)
print(stdout.read().decode(errors='replace'), flush=True)

print("\n=== run pytest grid9 + v1 ===", flush=True)
cmd = (f"docker exec {DEPLOY_ID}-backend bash -c "
       f"'cd /app && python -m pytest tests/test_merchant_dashboard_grid9.py tests/test_merchant_dashboard_v1.py -v 2>&1' | tail -100")
_, stdout, _ = cli.exec_command(cmd, timeout=300)
out = stdout.read().decode(errors='replace')
print(out, flush=True)

passed = "passed" in out and "failed" not in out
print(f"\n=== pytest result: {'PASS' if passed else 'FAIL'} ===\n", flush=True)

# 烟雾测试 API
print("=== API smoke tests ===", flush=True)
results = []
endpoints = [
    ("/api/merchant/dashboard/time-slots", "GET", None, 200),
    ("/admin/product-system/orders/dashboard/", "GET", None, 200),
    ("/admin/", "GET", None, [200, 308]),
]
for path, method, body, expected in endpoints:
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method=method)
        if body:
            req.data = body
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
        ok = (code == expected) if isinstance(expected, int) else (code in expected)
        results.append((path, code, ok))
        print(f"  {'✓' if ok else '✗'} {method} {path} -> {code}", flush=True)
    except Exception as e:
        results.append((path, str(e), False))
        print(f"  ✗ {method} {path} -> {e}", flush=True)

all_ok = all(r[2] for r in results)
print(f"\n=== final: {'ALL PASS' if all_ok and passed else 'CHECK'} ===\n")

cli.close()
sys.exit(0 if all_ok and passed else 1)
