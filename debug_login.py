import httpx

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
client = httpx.Client(timeout=30, verify=False)

print("--- Testing Login Methods ---")

# Try SMS code
r = client.post(f"{BASE}/auth/sms-code", json={"phone": "13800138000"})
print(f"1. POST /auth/sms-code: status={r.status_code}, body={r.text[:300]}")

# Try SMS login
r2 = client.post(f"{BASE}/auth/sms-login", json={"phone": "13800138000", "code": "888888"})
print(f"2. POST /auth/sms-login: status={r2.status_code}, body={r2.text[:300]}")

# Try password login
r3 = client.post(f"{BASE}/auth/login", json={"phone": "13800138000", "password": "admin123"})
print(f"3. POST /auth/login: status={r3.status_code}, body={r3.text[:300]}")

# Try different password format
r4 = client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
print(f"4. POST /auth/login (username): status={r4.status_code}, body={r4.text[:300]}")

# Check openapi
r5 = client.get(f"{BASE}/openapi.json")
if r5.status_code == 200:
    import json
    spec = r5.json()
    paths = [p for p in spec.get("paths", {}).keys() if "auth" in p.lower() or "login" in p.lower()]
    print(f"5. Auth paths in openapi: {paths}")
else:
    print(f"5. openapi.json: status={r5.status_code}")

# Try sms-code with form data
r6 = client.post(f"{BASE}/auth/send-code", json={"phone": "13800138000"})
print(f"6. POST /auth/send-code: status={r6.status_code}, body={r6.text[:300]}")

# Try token endpoint
r7 = client.post(f"{BASE}/auth/token", data={"username": "13800138000", "password": "admin123"})
print(f"7. POST /auth/token: status={r7.status_code}, body={r7.text[:300]}")
