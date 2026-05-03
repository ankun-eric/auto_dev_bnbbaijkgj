"""Quick URL health check for the deployed coupon-v2.2 feature."""
import urllib.request
import urllib.error
import json

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    ("frontend root", f"{BASE}/"),
    ("admin login", f"{BASE}/admin/login"),
    ("admin coupons page", f"{BASE}/admin/product-system/coupons"),
    ("api health", f"{BASE}/api/health"),
    ("api type-descriptions (auth required, expect 401/403)",
     f"{BASE}/api/admin/coupons/type-descriptions"),
    ("api scope-limits (auth required, expect 401/403)",
     f"{BASE}/api/admin/coupons/scope-limits"),
    ("api category-tree (auth required, expect 401/403)",
     f"{BASE}/api/admin/coupons/category-tree"),
    ("api product-picker (auth required, expect 401/403)",
     f"{BASE}/api/admin/coupons/product-picker?page=1&page_size=1"),
    ("api active-product-count (auth required, expect 401/403)",
     f"{BASE}/api/admin/coupons/active-product-count"),
]


def check(label, url):
    req = urllib.request.Request(url, headers={"User-Agent": "url-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.getcode(), len(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception as e:
        return f"ERR:{e.__class__.__name__}", 0


passed = 0
total = 0
results = []
for label, url in URLS:
    code, size = check(label, url)
    total += 1
    # For protected endpoints, 401/403 means the route exists; for unprotected, 200 expected
    if "auth required" in label:
        ok = code in (401, 403)
    else:
        ok = code == 200
    if ok:
        passed += 1
    mark = "OK" if ok else "FAIL"
    results.append((mark, code, size, label, url))
    print(f"[{mark:4s}] code={code} size={size:>7} {label}")

print(f"\n=== {passed}/{total} OK ===")
