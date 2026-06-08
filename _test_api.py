import urllib.request
import urllib.error
import sys
import json

# Test 1: Health check
print("=== Test 1: /api/health ===")
try:
    r = urllib.request.urlopen("http://localhost:8000/api/health", timeout=10)
    print(r.read().decode()[:500])
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Calendar endpoint (requires auth, should return 401)
print("\n=== Test 2: /api/medication/calendar ===")
try:
    r = urllib.request.urlopen("http://localhost:8000/api/medication/calendar?year=2026&month=6", timeout=10)
    print("Status:", r.status)
    print(r.read().decode()[:500])
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    if e.code == 401:
        print("OK - endpoint exists, requires auth")
    elif e.code == 404:
        print("BAD - endpoint not found!")
    else:
        print(f"Unexpected: {e.code}")

# Test 3: Check medication endpoints in OpenAPI
print("\n=== Test 3: OpenAPI medication paths ===")
try:
    r = urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=10)
    data = json.loads(r.read().decode())
    paths = data.get("paths", {})
    med_paths = sorted([p for p in paths if "medication" in p.lower()])
    for p in med_paths:
        methods = list(paths[p].keys())
        print(f"  {p}: {methods}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 4: Records endpoint (requires auth)
print("\n=== Test 4: /api/medication/records ===")
try:
    r = urllib.request.urlopen("http://localhost:8000/api/medication/records?date=2026-06-01", timeout=10)
    print("Status:", r.status)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    if e.code == 401:
        print("OK - endpoint exists, requires auth")
    elif e.code == 404:
        print("BAD - endpoint not found!")

# Test 5: Supplement endpoint
print("\n=== Test 5: /api/medication/supplement (POST) ===")
try:
    req = urllib.request.Request("http://localhost:8000/api/medication/supplement", method="POST")
    r = urllib.request.urlopen(req, timeout=10)
    print("Status:", r.status)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    if e.code == 401:
        print("OK - endpoint exists, requires auth")
    elif e.code == 422:
        print("OK - endpoint exists, validation error (expected without body)")
    elif e.code == 404:
        print("BAD - endpoint not found!")
