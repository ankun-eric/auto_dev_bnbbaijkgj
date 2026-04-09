"""Server deployment verification for voice search optimization."""
import requests
import sys

requests.packages.urllib3.disable_warnings()

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} - {detail}")

print("=== Voice Search Deployment Verification ===\n")

# TC-001: H5 homepage accessible
try:
    r = requests.get(f"{BASE}/", verify=False, timeout=15)
    check("TC-001 H5 homepage", r.status_code == 200, f"status={r.status_code}")
except Exception as e:
    check("TC-001 H5 homepage", False, str(e))

# TC-002: Search page accessible
try:
    r = requests.get(f"{BASE}/search", verify=False, timeout=15, allow_redirects=True)
    check("TC-002 Search page", r.status_code == 200, f"status={r.status_code}")
except Exception as e:
    check("TC-002 Search page", False, str(e))

# TC-003: API health
try:
    r = requests.get(f"{BASE}/api/health", verify=False, timeout=15)
    check("TC-003 API health", r.status_code == 200, f"status={r.status_code}")
except Exception as e:
    check("TC-003 API health", False, str(e))

# TC-004: ASR token endpoint available
try:
    r = requests.post(f"{BASE}/api/search/asr/token", verify=False, timeout=15)
    check("TC-004 ASR token endpoint", r.status_code in [200, 401, 422], f"status={r.status_code}")
except Exception as e:
    check("TC-004 ASR token endpoint", False, str(e))

# TC-005: Search suggest endpoint
try:
    r = requests.get(f"{BASE}/api/search/suggest?q=test", verify=False, timeout=15)
    check("TC-005 Search suggest", r.status_code in [200, 401], f"status={r.status_code}")
except Exception as e:
    check("TC-005 Search suggest", False, str(e))

# TC-006: Hot search endpoint
try:
    r = requests.get(f"{BASE}/api/search/hot", verify=False, timeout=15)
    check("TC-006 Hot search", r.status_code in [200, 401], f"status={r.status_code}")
except Exception as e:
    check("TC-006 Hot search", False, str(e))

# TC-007: ASR recognize endpoint (should accept POST with form data)
try:
    r = requests.post(f"{BASE}/api/search/asr/recognize", verify=False, timeout=15)
    check("TC-007 ASR recognize endpoint", r.status_code in [200, 400, 401, 422], f"status={r.status_code}")
except Exception as e:
    check("TC-007 ASR recognize endpoint", False, str(e))

print(f"\n=== Results: {passed} passed, {failed} failed ===")
sys.exit(1 if failed > 0 else 0)
