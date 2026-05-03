#!/usr/bin/env python3
"""Run T01-T09 backend API tests against the public URL."""
import json
import sys
import urllib.request
import urllib.error
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
API = BASE + "/api"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def req(method, path, token=None, body=None, follow_redirect=True):
    url = path if path.startswith("http") else (API + path)
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), dict(e.headers or {})
    except Exception as e:
        return -1, f"ERROR: {e}", {}


def head(path):
    url = path if path.startswith("http") else (BASE + path)
    r = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return -1


def jload(s):
    try:
        return json.loads(s)
    except Exception:
        return None


results = []


def record(name, ok, detail):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}")
    results.append((name, ok, detail))


# 0. Login
print("=== Login ===")
code, body, _ = req("POST", "/admin/login", body={"phone": "13800000000", "password": "admin123"})
print(f"  status={code}")
print(f"  body={body[:300]}")
data = jload(body) or {}
token = data.get("access_token") or data.get("token")
if not token:
    print("FATAL: cannot get admin token")
    sys.exit(1)
print(f"  token len={len(token)}")

# Get product categories
print("\n=== Product categories ===")
code, body, _ = req("GET", "/admin/products/categories", token=token)
print(f"  status={code}")
print(f"  body[:400]={body[:400]}")
pc = jload(body)
PCID = None
if isinstance(pc, list) and pc:
    PCID = pc[0].get("id")
elif isinstance(pc, dict):
    items = pc.get("items") or pc.get("data") or pc.get("categories") or []
    if items:
        PCID = items[0].get("id")
print(f"  PCID={PCID}")

# Get merchant categories
print("\n=== Merchant categories ===")
code, body, _ = req("GET", "/admin/merchant-categories", token=token)
print(f"  status={code}")
print(f"  body[:400]={body[:400]}")
mc = jload(body)
MCID = None
if isinstance(mc, list) and mc:
    MCID = mc[0].get("id")
elif isinstance(mc, dict):
    items = mc.get("items") or mc.get("data") or mc.get("categories") or []
    if items:
        MCID = items[0].get("id")
print(f"  MCID={MCID}")

if not MCID:
    print("FATAL: cannot get MCID")
    sys.exit(1)

# T01: Create store with business hours + scope
print("\n=== T01: Create store with business_start/business_end/business_scope ===")
payload = {
    "store_name": "BUGFIX测试门店",
    "category_id": MCID,
    "lat": 23.0,
    "lng": 113.0,
    "business_start": "09:00",
    "business_end": "22:00",
    "business_scope": [PCID] if PCID else [],
}
code, body, _ = req("POST", "/admin/merchant/stores", token=token, body=payload)
print(f"  status={code}")
print(f"  body={body[:600]}")
sid = None
ok = False
if code in (200, 201):
    d = jload(body) or {}
    sid = d.get("id") or (d.get("data") or {}).get("id")
    bs = d.get("business_start") or (d.get("data") or {}).get("business_start")
    be = d.get("business_end") or (d.get("data") or {}).get("business_end")
    sc = d.get("business_scope") or (d.get("data") or {}).get("business_scope")
    ok = sid is not None and bs in ("09:00", "09:00:00") and be in ("22:00", "22:00:00")
    record("T01-create", ok, f"sid={sid} business_start={bs} business_end={be} scope={sc}")
else:
    record("T01-create", False, f"HTTP {code}: {body[:200]}")

if not sid:
    print("Cannot continue without SID; trying to find one")
    code, body, _ = req("GET", "/admin/merchant/stores", token=token)
    d = jload(body) or {}
    items = d.get("items") if isinstance(d, dict) else d
    if items:
        sid = items[0].get("id")
        print(f"  Using existing sid={sid}")

if sid:
    # Verify GET
    code, body, _ = req("GET", f"/admin/merchant/stores/{sid}", token=token)
    d = jload(body) or {}
    bs = d.get("business_start")
    be = d.get("business_end")
    sc = d.get("business_scope")
    ok = bs in ("09:00", "09:00:00") and be in ("22:00", "22:00:00")
    record("T01-get-verify", ok, f"business_start={bs} business_end={be} scope={sc}")

    # T02: change only hours
    print("\n=== T02: change only hours ===")
    code, body, _ = req("PUT", f"/admin/merchant/stores/{sid}", token=token,
                        body={"business_start": "10:00", "business_end": "20:30"})
    record("T02-update-hours", code == 200, f"status={code} body={body[:200]}")
    code, body, _ = req("GET", f"/admin/merchant/stores/{sid}", token=token)
    d = jload(body) or {}
    bs = d.get("business_start")
    be = d.get("business_end")
    record("T02-verify", bs in ("10:00", "10:00:00") and be in ("20:30", "20:30:00"),
           f"business_start={bs} business_end={be}")

    # T03: change only scope to []
    print("\n=== T03: change only scope ===")
    code, body, _ = req("PUT", f"/admin/merchant/stores/{sid}", token=token,
                        body={"business_scope": []})
    record("T03-update-scope", code == 200, f"status={code} body={body[:200]}")
    code, body, _ = req("GET", f"/admin/merchant/stores/{sid}", token=token)
    d = jload(body) or {}
    sc = d.get("business_scope")
    record("T03-verify", isinstance(sc, list) and len(sc) == 0, f"business_scope={sc}")

    # T04: end <= start should be 400
    print("\n=== T04: end <= start ===")
    code, body, _ = req("PUT", f"/admin/merchant/stores/{sid}", token=token,
                        body={"business_start": "12:00", "business_end": "12:00"})
    record("T04-end-le-start", code == 400, f"status={code} body={body[:200]}")

    # T05: not on 30 min boundary
    print("\n=== T05: not on 30 min boundary ===")
    code, body, _ = req("PUT", f"/admin/merchant/stores/{sid}", token=token,
                        body={"business_start": "09:15", "business_end": "22:00"})
    record("T05-not-30min", code == 400, f"status={code} body={body[:200]}")

    # T06: out of 07:00-22:00 range
    print("\n=== T06: out of 07:00-22:00 ===")
    code, body, _ = req("PUT", f"/admin/merchant/stores/{sid}", token=token,
                        body={"business_start": "06:00", "business_end": "22:00"})
    record("T06-out-of-range", code == 400, f"status={code} body={body[:200]}")

    # T07: list returns new fields
    print("\n=== T07: list returns business fields ===")
    code, body, _ = req("GET", "/admin/merchant/stores", token=token)
    d = jload(body) or {}
    items = d.get("items") if isinstance(d, dict) else d
    has_fields = False
    sample = None
    if items:
        sample = items[0]
        has_fields = "business_start" in sample and "business_end" in sample and "business_scope" in sample
    record("T07-list-fields", has_fields, f"sample_keys={list(sample.keys()) if sample else None}")

    # T08: compatibility route
    print("\n=== T08: compat route /admin/stores/{id}/business-scope ===")
    payload_t8 = {"business_scope": [PCID] if PCID else []}
    code, body, _ = req("PUT", f"/admin/stores/{sid}/business-scope", token=token, body=payload_t8)
    d = jload(body) or {}
    deprecated = d.get("deprecated") if isinstance(d, dict) else None
    record("T08-compat-route", code == 200 and deprecated is True,
           f"status={code} deprecated={deprecated} body={body[:200]}")

# T09: page accessibility (use GET with follow-redirect, not HEAD)
print("\n=== T09: front page reachability (GET + follow) ===")
import urllib.request as _ur


def get_follow(path):
    url = path if path.startswith("http") else (BASE + path)
    r = _ur.Request(url, method="GET",
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
    try:
        with _ur.urlopen(r, context=CTX, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return -1


# Note: h5-web basePath is /autodev/<id>/ (no /h5 segment), so the actual H5
# store-settings page is /merchant/store-settings (and /merchant/m/store-settings).
for path in ["/", "/admin/merchant/stores", "/merchant/store-settings",
             "/merchant/m/store-settings"]:
    s = get_follow(path)
    record(f"T09{path}", s == 200, f"status={s}")

print("\n\n========== SUMMARY ==========")
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
for n, ok, d in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {n}")
print(f"\n{passed}/{total} passed")
sys.exit(0 if passed == total else 1)
