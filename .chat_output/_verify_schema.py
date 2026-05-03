import urllib.request
import json
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

with urllib.request.urlopen(f"{BASE}/api/openapi.json", context=ctx, timeout=30) as resp:
    spec = json.loads(resp.read().decode("utf-8"))

text = json.dumps(spec)
print("'on_site' occurs in openapi:", text.count("on_site"))
print("'service_address_id' occurs:", text.count("service_address_id"))
print("'service_address_snapshot' occurs:", text.count("service_address_snapshot"))

# Find FulfillmentType
schemas = spec.get("components", {}).get("schemas", {})
for name, s in schemas.items():
    if "Fulfillment" in name:
        print(f"\n  schema {name}: {json.dumps(s, ensure_ascii=False)[:300]}")
    enum_vals = s.get("enum", [])
    if "on_site" in enum_vals:
        print(f"\n  enum schema {name}: {enum_vals}")

# UnifiedOrderResponse fields
uor = schemas.get("UnifiedOrderResponse")
if uor:
    props = list(uor.get("properties", {}).keys())
    print(f"\n  UnifiedOrderResponse props: {props}")

# Check products list returns
with urllib.request.urlopen(f"{BASE}/api/products?page=1&page_size=2", context=ctx, timeout=30) as resp:
    d = json.loads(resp.read())
print("\n  products list sample:", json.dumps(d, ensure_ascii=False)[:600])
