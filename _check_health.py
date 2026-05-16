import requests
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
try:
    r = requests.get(f"{BASE}/api/health", timeout=15)
    print("health:", r.status_code, r.text[:200])
except Exception as e:
    print("err:", e)
