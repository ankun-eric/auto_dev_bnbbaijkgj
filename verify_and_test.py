import requests
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE_URL}/api"

print('=== Health Check ===')
for attempt in range(5):
    try:
        r = requests.get(f"{API}/health", verify=False, timeout=10)
        print(f'Health check: {r.status_code} - {r.text[:100]}')
        if r.status_code == 200:
            break
    except Exception as e:
        print(f'Attempt {attempt+1} failed: {e}')
    time.sleep(5)
