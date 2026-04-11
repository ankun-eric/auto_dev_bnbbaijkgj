import requests
import json
import random
import string
import time

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"

results = []
token = None
member_id = None
session_id = None

def log(tc, passed, detail="", response=None):
    status = "PASS" if passed else "FAIL"
    resp_text = ""
    if response is not None:
        try:
            resp_text = json.dumps(response.json(), ensure_ascii=False, indent=2)
        except:
            resp_text = response.text[:500]
    results.append({
        "tc": tc,
        "passed": passed,
        "detail": detail,
        "response": resp_text
    })
    print(f"[{status}] {tc}: {detail}")
    if not passed:
        print(f"  Response: {resp_text[:300]}")

def rand_phone():
    return "1" + "".join(random.choices(string.digits, k=10))

# TC-000: Health check
def tc_000_health():
    try:
        r = requests.get(f"{BASE_URL}/auth/health", timeout=10)
        if r.status_code == 200:
            log("TC-000", True, f"Health OK: {r.text[:100]}", r)
        else:
            log("TC-000", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-000", False, f"Exception: {e}")

# TC-001: Register and login
def tc_001_register_login():
    global token
    phone = rand_phone()
    # Try register
    payload = {
        "phone": phone,
        "password": "Test1234!",
        "nickname": "TestUser",
        "verification_code": "123456"
    }
    # First try to discover register endpoint
    for path in ["/auth/register", "/users/register", "/auth/signup"]:
        try:
            r = requests.post(f"{BASE_URL}{path}", json=payload, timeout=10)
            if r.status_code in (200, 201):
                data = r.json()
                token = data.get("access_token") or (data.get("data") or {}).get("access_token")
                if token:
                    log("TC-001", True, f"Registered via {path}, got token", r)
                    return
        except:
            pass

    # Try login with existing test account
    login_payloads = [
        {"phone": "13800000001", "password": "Test1234!"},
        {"username": "test", "password": "test123"},
    ]
    for path in ["/auth/login", "/users/login", "/auth/token"]:
        for lp in login_payloads:
            try:
                r = requests.post(f"{BASE_URL}{path}", json=lp, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    token = data.get("access_token") or (data.get("data") or {}).get("access_token")
                    if token:
                        log("TC-001", True, f"Logged in via {path}", r)
                        return
            except:
                pass

    # Try send-code + register flow
    phone2 = rand_phone()
    try:
        sc = requests.post(f"{BASE_URL}/auth/send-code", json={"phone": phone2}, timeout=10)
        print(f"  send-code status: {sc.status_code}, body: {sc.text[:200]}")
    except Exception as e:
        print(f"  send-code exception: {e}")

    # Try register without verification code
    for path in ["/auth/register", "/users/register"]:
        try:
            r = requests.post(f"{BASE_URL}{path}", json={"phone": phone2, "password": "Test1234!", "nickname": "TestUser"}, timeout=10)
            print(f"  {path} status: {r.status_code}, body: {r.text[:200]}")
            if r.status_code in (200, 201):
                data = r.json()
                token = data.get("access_token") or (data.get("data") or {}).get("access_token")
                if token:
                    log("TC-001", True, f"Registered via {path} (no code)", r)
                    return
        except Exception as e:
            print(f"  {path} exception: {e}")

    log("TC-001", False, "Could not register or login - no token obtained")

# TC-002: Create family member with new fields
def tc_002_create_member():
    global member_id
    if not token:
        log("TC-002", False, "Skipped - no token")
        return
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "relationship_type": "父亲",
        "nickname": "测试爸爸",
        "gender": "男",
        "height": 175.0,
        "weight": 70.0,
        "medical_histories": ["高血压"],
        "allergies": ["青霉素"]
    }
    try:
        r = requests.post(f"{BASE_URL}/family/members", json=payload, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            member_id = data.get("id") or (data.get("data") or {}).get("id")
            if member_id:
                log("TC-002", True, f"Created member id={member_id}", r)
            else:
                log("TC-002", False, "No id in response", r)
        else:
            log("TC-002", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-002", False, f"Exception: {e}")

# TC-003: Get single family member
def tc_003_get_member():
    if not token or not member_id:
        log("TC-003", False, "Skipped - no token or member_id")
        return
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/family/members/{member_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            has_fields = all(k in data for k in ["id", "nickname", "gender", "height", "weight"])
            log("TC-003", has_fields, f"Got member, fields present={has_fields}", r)
        else:
            log("TC-003", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-003", False, f"Exception: {e}")

# TC-004: Update family member
def tc_004_update_member():
    if not token or not member_id:
        log("TC-004", False, "Skipped - no token or member_id")
        return
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "height": 176.0,
        "medical_histories": ["高血压", "糖尿病（2型）"]
    }
    try:
        r = requests.put(f"{BASE_URL}/family/members/{member_id}", json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            updated_height = data.get("height")
            log("TC-004", updated_height == 176.0, f"Updated height={updated_height}", r)
        else:
            log("TC-004", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-004", False, f"Exception: {e}")

# TC-005: Create chat session with family_member_id and symptom_info
def tc_005_create_session():
    global session_id
    if not token or not member_id:
        log("TC-005", False, "Skipped - no token or member_id")
        return
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "session_type": "symptom_check",
        "family_member_id": member_id,
        "title": "头部·头痛·持续2天",
        "symptom_info": {
            "body_part": "head",
            "body_part_label": "头部",
            "symptoms": ["头痛", "头晕"],
            "duration": "1-3天"
        }
    }
    try:
        r = requests.post(f"{BASE_URL}/chat/sessions", json=payload, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            session_id = data.get("id") or (data.get("data") or {}).get("id")
            has_fields = session_id and "family_member_id" in data
            log("TC-005", bool(has_fields), f"Created session id={session_id}, family_member_id={data.get('family_member_id')}", r)
        else:
            log("TC-005", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-005", False, f"Exception: {e}")

# TC-006: Switch member in session
def tc_006_switch_member():
    if not token or not session_id:
        log("TC-006", False, "Skipped - no token or session_id")
        return
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"family_member_id": None}
    try:
        r = requests.post(f"{BASE_URL}/chat/sessions/{session_id}/switch-member", json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            log("TC-006", True, f"Switched member OK", r)
        else:
            log("TC-006", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-006", False, f"Exception: {e}")

# TC-007: Update health profile for member
def tc_007_health_profile_member():
    if not token or not member_id:
        log("TC-007", False, "Skipped - no token or member_id")
        return
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "height": 175.0,
        "weight": 70.0,
        "gender": "男",
        "medical_histories": ["高血压"]
    }
    try:
        r = requests.put(f"{BASE_URL}/health/profile/member/{member_id}", json=payload, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            log("TC-007", True, f"Health profile updated", r)
        else:
            log("TC-007", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-007", False, f"Exception: {e}")

# TC-008: Get health profile for member
def tc_008_get_health_profile_member():
    if not token or not member_id:
        log("TC-008", False, "Skipped - no token or member_id")
        return
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/health/profile/member/{member_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            log("TC-008", True, f"Got health profile for member", r)
        else:
            log("TC-008", False, f"Status {r.status_code}", r)
    except Exception as e:
        log("TC-008", False, f"Exception: {e}")

# Run all tests
print("=" * 60)
print("Starting API Tests")
print(f"BASE_URL: {BASE_URL}")
print("=" * 60)

tc_000_health()
tc_001_register_login()
tc_002_create_member()
tc_003_get_member()
tc_004_update_member()
tc_005_create_session()
tc_006_switch_member()
tc_007_health_profile_member()
tc_008_get_health_profile_member()

print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])
print(f"Total: {len(results)}  PASS: {passed}  FAIL: {failed}")
print()

for r in results:
    status = "PASS" if r["passed"] else "FAIL"
    print(f"[{status}] {r['tc']}: {r['detail']}")

if failed > 0:
    print("\n" + "=" * 60)
    print("FAILED TEST DETAILS")
    print("=" * 60)
    for r in results:
        if not r["passed"]:
            print(f"\n### {r['tc']} FAILED")
            print(f"Detail: {r['detail']}")
            if r["response"]:
                print(f"Response:\n{r['response'][:800]}")
