#!/usr/bin/env python3
"""校验睡眠相关 H5 路由与后端健康接口可达性（经网关）"""
import urllib.request
import ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    f"{BASE}/health-profile",
    f"{BASE}/health-metric/sleep",
    f"{BASE}/health-metric/sleep?profileId=1",
    f"{BASE}/api/docs",
]
for u in urls:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            body = r.read(400).decode("utf-8", "replace")
            print(f"[{r.status}] {u}")
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {u}")
    except Exception as e:
        print(f"[ERR {type(e).__name__}: {e}] {u}")
