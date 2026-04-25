"""验证关键链接可达性。"""
import sys
import urllib3
import requests

urllib3.disable_warnings()

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    f"{BASE}/",
    f"{BASE}/checkup",
    f"{BASE}/login",
    f"{BASE}/chat/test-id?type=report_interpret",
    f"{BASE}/api/health",
]

ok = True
for u in URLS:
    try:
        r = requests.get(u, timeout=15, verify=False, allow_redirects=False)
        sc = r.status_code
        flag = "OK" if sc in (200, 301, 302, 304, 307, 308, 401, 403) else "BAD"
        if flag == "BAD":
            ok = False
        print(f"[{flag}] {sc}  {u}")
    except Exception as e:
        ok = False
        print(f"[ERR] {u}  -> {e}")

sys.exit(0 if ok else 1)
