#!/usr/bin/env python3
"""Verify deployment URLs are reachable."""
import urllib.request
import ssl
import json

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    (f"{BASE}/", "H5 Homepage"),
    (f"{BASE}/admin/", "Admin Homepage"),
    (f"{BASE}/api/health", "API Health Check"),
    (f"{BASE}/api/app-settings/page-style", "Page Style API"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = []
for url, name in URLS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DeployChecker/1.0"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        code = resp.getcode()
        body = resp.read(500).decode('utf-8', errors='replace')
        status = "OK" if code == 200 else f"WARN({code})"
        print(f"[{status}] {name}: {url} -> HTTP {code}")
        if "api" in url.lower():
            print(f"  Body: {body[:200]}")
        results.append((url, name, code, True))
    except Exception as e:
        print(f"[FAIL] {name}: {url} -> {e}")
        results.append((url, name, 0, False))

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
ok = sum(1 for _, _, _, s in results if s)
total = len(results)
print(f"Passed: {ok}/{total}")
for url, name, code, success in results:
    icon = "PASS" if success else "FAIL"
    print(f"  [{icon}] {name}: HTTP {code} - {url}")

if ok < total:
    print("\nSome URLs failed!")
    exit(1)
else:
    print("\nAll URLs reachable!")
    exit(0)
