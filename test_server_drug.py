import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
results = []

def test(name, func):
    try:
        r = func()
        results.append(f"PASS: {name}")
        return r
    except AssertionError as e:
        results.append(f"FAIL: {name} - {e}")
    except Exception as e:
        results.append(f"ERROR: {name} - {e}")

# 1. Health check
def t1():
    r = requests.get(f"{BASE}/health", verify=False)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
test("Health check", t1)

# 2. Admin login
admin_token = None
def t2():
    global admin_token
    r = requests.post(f"{BASE}/auth/login", json={"phone": "13800000000", "password": "admin123"}, verify=False)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    admin_token = r.json()["access_token"]
    return admin_token
test("Admin login", t2)

# 3. Drug identify history - no auth
def t3():
    r2 = requests.get(f"{BASE}/drug-identify/history", verify=False)
    assert r2.status_code in [401, 403]
test("Drug history - no auth -> 401", t3)

# 4. Drug identify history - with auth
def t4():
    r = requests.get(f"{BASE}/drug-identify/history", headers={"Authorization": f"Bearer {admin_token}"}, params={"page": 1, "page_size": 10}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
test("Drug history - with auth -> 200", t4)

# 5. Drug details statistics
def t5():
    r = requests.get(f"{BASE}/admin/drug-details/statistics", headers={"Authorization": f"Bearer {admin_token}"}, verify=False)
    assert r.status_code == 200
test("Drug details statistics", t5)

# 6. Drug details list
def t6():
    r = requests.get(f"{BASE}/admin/drug-details", headers={"Authorization": f"Bearer {admin_token}"}, params={"page": 1, "page_size": 10}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
test("Drug details list", t6)

# 7. Drug detail conversation - 404
def t7():
    r = requests.get(f"{BASE}/admin/drug-details/99999/conversation", headers={"Authorization": f"Bearer {admin_token}"}, verify=False)
    assert r.status_code == 404
test("Drug detail conversation - 404", t7)

# 8. Drug detail conversation - no auth
def t8():
    r = requests.get(f"{BASE}/admin/drug-details/1/conversation", verify=False)
    assert r.status_code in [401, 403]
test("Drug detail conversation - no auth -> 401", t8)

# 9. Drug history pagination
def t9():
    r = requests.get(f"{BASE}/drug-identify/history", headers={"Authorization": f"Bearer {admin_token}"}, params={"page": 2, "page_size": 5}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
test("Drug history pagination", t9)

# 10. H5 page accessible
def t10():
    r = requests.get("https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/", verify=False)
    assert r.status_code == 200
test("H5 page accessible", t10)

# 11. Admin page accessible
def t11():
    r = requests.get("https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/", verify=False)
    assert r.status_code == 200
test("Admin page accessible", t11)

print("\n=== Test Results ===")
passed = sum(1 for r in results if r.startswith("PASS"))
failed = sum(1 for r in results if r.startswith("FAIL") or r.startswith("ERROR"))
for r in results:
    print(r)
print(f"\nTotal: {len(results)}, Passed: {passed}, Failed: {failed}")
