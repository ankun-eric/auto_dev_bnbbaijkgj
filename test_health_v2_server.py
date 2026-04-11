"""Server API tests for health profile v2 feature"""
import requests
import json
import sys

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

PASS = 0
FAIL = 0
results = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        results.append(f"  PASS  {name}")
    else:
        FAIL += 1
        results.append(f"  FAIL  {name}" + (f" | {detail}" if detail else ""))

def get_admin_token():
    resp = requests.post(f"{BASE_URL}/api/admin/login",
                         json={"phone": "13800000000", "password": "admin123"}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token", "")
    return ""

def get_user_token():
    # Try SMS login with test code
    resp = requests.post(f"{BASE_URL}/api/auth/sms-code",
                         json={"phone": "13800138000"}, timeout=10)
    code = "123456"
    resp = requests.post(f"{BASE_URL}/api/auth/sms-login",
                         json={"phone": "13800138000", "code": code}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token", "")
    return ""

def test_health_endpoint():
    print("\n[1] Health Endpoint")
    resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
    check("GET /api/health returns 200", resp.status_code == 200, f"got {resp.status_code}")

def test_relation_types():
    print("\n[2] Relation Types")
    resp = requests.get(f"{BASE_URL}/api/relation-types", timeout=10)
    check("GET /api/relation-types returns 200", resp.status_code == 200, f"got {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        check("Response has 'items' field", "items" in data, str(data.keys()))
        if "items" in data:
            items = data["items"]
            check("Has >= 10 relation types", len(items) >= 10, f"got {len(items)}")
            if items:
                item = items[0]
                check("Item has 'id' field", "id" in item)
                check("Item has 'name' field", "name" in item)

def test_disease_presets():
    print("\n[3] Disease Presets")
    for category in ["chronic", "genetic"]:
        resp = requests.get(f"{BASE_URL}/api/disease-presets?category={category}", timeout=10)
        check(f"GET /api/disease-presets?category={category} returns 200",
              resp.status_code == 200, f"got {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            check(f"{category}: has 'items' field", "items" in data)
            if "items" in data:
                items = data["items"]
                check(f"{category}: has >= 3 items", len(items) >= 3, f"got {len(items)}")

def test_admin_endpoints():
    print("\n[4] Admin Endpoints")
    token = get_admin_token()
    check("Admin login succeeds", bool(token), "empty token")
    if token:
        headers = {"Authorization": f"Bearer {token}"}

        # Admin relation types CRUD
        resp = requests.get(f"{BASE_URL}/api/admin/relation-types", headers=headers, timeout=10)
        check("GET /api/admin/relation-types returns 200", resp.status_code == 200, f"got {resp.status_code}")

        # Create a test relation type
        resp = requests.post(f"{BASE_URL}/api/admin/relation-types", headers=headers,
                             json={"name": "测试关系_autotest", "sort_order": 999}, timeout=10)
        check("POST /api/admin/relation-types creates item",
              resp.status_code in [200, 201], f"got {resp.status_code}: {resp.text[:200]}")
        if resp.status_code in [200, 201]:
            rid = resp.json().get("id")
            if rid:
                # Update
                resp2 = requests.put(f"{BASE_URL}/api/admin/relation-types/{rid}", headers=headers,
                                     json={"name": "测试关系_updated", "sort_order": 999}, timeout=10)
                check("PUT /api/admin/relation-types/{id} updates item",
                      resp2.status_code == 200, f"got {resp2.status_code}: {resp2.text[:200]}")
                # Delete
                resp3 = requests.delete(f"{BASE_URL}/api/admin/relation-types/{rid}",
                                        headers=headers, timeout=10)
                check("DELETE /api/admin/relation-types/{id} deletes item",
                      resp3.status_code in [200, 204], f"got {resp3.status_code}")

        # Admin disease presets
        resp = requests.get(f"{BASE_URL}/api/admin/disease-presets", headers=headers, timeout=10)
        check("GET /api/admin/disease-presets returns 200",
              resp.status_code == 200, f"got {resp.status_code}")

        # Admin health records
        resp = requests.get(f"{BASE_URL}/api/admin/health/users", headers=headers, timeout=10)
        check("GET /api/admin/health/users returns 200",
              resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

def test_family_members():
    print("\n[5] Family Member API")
    token = get_user_token()
    if not token:
        print("  SKIP  (no user token available)")
        return
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/api/family/members", headers=headers, timeout=10)
    check("GET /api/family/members returns 200",
          resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

def test_frontend_pages():
    print("\n[6] Frontend Pages")
    pages = [
        (f"{BASE_URL}/", "H5 home page"),
        (f"{BASE_URL}/admin/", "Admin home page"),
        (f"{BASE_URL}/admin/health-records", "Admin health records page"),
        (f"{BASE_URL}/admin/relation-types", "Admin relation types page"),
        (f"{BASE_URL}/admin/disease-presets", "Admin disease presets page"),
    ]
    for url, name in pages:
        try:
            resp = requests.get(url, timeout=15, allow_redirects=True)
            check(f"{name} accessible (200/3xx)", resp.status_code in [200, 301, 302], f"got {resp.status_code}")
        except Exception as e:
            check(f"{name} accessible", False, str(e))

if __name__ == "__main__":
    print("=" * 60)
    print("Health Profile V2 - Server API Tests")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    test_health_endpoint()
    test_relation_types()
    test_disease_presets()
    test_admin_endpoints()
    test_family_members()
    test_frontend_pages()

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    for r in results:
        print(r)
    print(f"\nTotal: {PASS + FAIL} | PASS: {PASS} | FAIL: {FAIL}")

    sys.exit(0 if FAIL == 0 else 1)
