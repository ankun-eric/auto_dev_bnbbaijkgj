"""Smoke test: verify deployed endpoints are reachable + new fields work."""
import urllib.request
import urllib.error
import json
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

ENDPOINTS = [
    ("admin-web home", f"{BASE}/admin/login"),
    ("h5 home", f"{BASE}/h5"),
    ("h5 services", f"{BASE}/h5/services"),
    ("backend healthz", f"{BASE}/api/healthz"),
    ("backend openapi", f"{BASE}/api/openapi.json"),
    ("backend products list", f"{BASE}/api/products?page=1&page_size=5"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = []
for name, url in ENDPOINTS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            code = resp.getcode()
            body = resp.read(2000)
            results.append((name, url, code, len(body), None))
            print(f"[OK ] {code}  {name}  ({len(body)} bytes)  {url}")
    except urllib.error.HTTPError as e:
        results.append((name, url, e.code, 0, str(e)))
        print(f"[ERR] {e.code}  {name}  {url}  {e}")
    except Exception as e:
        results.append((name, url, 0, 0, str(e)))
        print(f"[ERR] ---  {name}  {url}  {e}")

# Verify openapi has fields
try:
    req = urllib.request.Request(f"{BASE}/api/openapi.json")
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        spec = json.loads(resp.read().decode("utf-8"))
    schemas = spec.get("components", {}).get("schemas", {})
    found = []
    # Look for FulfillmentType enum
    for name, s in schemas.items():
        if "fulfillment" in name.lower() or s.get("description", "").startswith("FulfillmentType"):
            enum_vals = s.get("enum", [])
            if enum_vals:
                print(f"  FulfillmentType candidate {name}: {enum_vals}")
                if "on_site" in enum_vals:
                    found.append(name)
    # Check UnifiedOrderResponse for service_address_id
    uor = schemas.get("UnifiedOrderResponse")
    if uor:
        props = uor.get("properties", {})
        has_sa = "service_address_id" in props and "service_address_snapshot" in props
        print(f"  UnifiedOrderResponse.service_address_id: {has_sa}")
    print(f"  enum schemas with on_site: {found}")
except Exception as e:
    print(f"  openapi check err: {e}")

failed = [r for r in results if r[2] not in (200, 401, 422)]
print(f"\nTotal: {len(results)}, failed: {len(failed)}")
for f in failed:
    print(f"  FAIL: {f}")
