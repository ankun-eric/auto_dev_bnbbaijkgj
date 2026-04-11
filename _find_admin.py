import paramiko
import requests
import urllib3
urllib3.disable_warnings()

# Try common passwords for admin
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
phone = "13800000000"
passwords = ["admin123", "123456", "Newbang888", "bini_health_2026", "admin@123", "Admin123", "password"]

for pwd in passwords:
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"phone": phone, "password": pwd}, verify=False)
    if resp.status_code == 200:
        print(f"SUCCESS: phone={phone}, password={pwd}")
        print("Token:", resp.json().get("access_token", "")[:50])
        break
    else:
        print(f"FAIL: {pwd} -> {resp.status_code} {resp.text[:80]}")
