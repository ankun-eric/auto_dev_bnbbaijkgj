import requests
import json

base = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

r = requests.get(f"{base}/api/settings/logo", timeout=15, verify=False)
print(f"GET /api/settings/logo: {r.status_code}")
print(f"Response: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
