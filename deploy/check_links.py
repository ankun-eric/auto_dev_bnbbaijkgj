import urllib.request
import ssl
import sys

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

LINKS = [
    (f"{BASE}/", "H5 Frontend"),
    (f"{BASE}/admin/", "Admin Frontend"),
    (f"{BASE}/api/health", "Backend Health"),
    (f"{BASE}/api/docs", "API Docs"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

all_ok = True
for url, name in LINKS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DeployCheck/1.0"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        code = resp.getcode()
        body = resp.read(500).decode('utf-8', errors='replace')
        if code >= 200 and code < 400:
            print(f"  OK  [{code}] {name}: {url}")
        else:
            print(f"  WARN [{code}] {name}: {url}")
            all_ok = False
    except Exception as e:
        print(f"  FAIL {name}: {url} -> {e}")
        all_ok = False

if all_ok:
    print("\nAll links are reachable!")
else:
    print("\nSome links failed!")
    sys.exit(1)
