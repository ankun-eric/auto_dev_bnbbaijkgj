"""
Non-UI automated tests for AI Model Config CRUD endpoints.
Target: deployed server via HTTPS gateway.
"""
import sys
import requests

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
LOGIN_URL = f"{BASE}/admin/login"
AI_CONFIG_URL = f"{BASE}/admin/ai-config"

results = []
created_config_id = None
token = None


def record(tc_id: str, name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append({"id": tc_id, "name": name, "passed": passed, "detail": detail})
    print(f"  [{status}] {tc_id}: {name}")
    if detail and not passed:
        print(f"         Detail: {detail}")


def get_auth_header():
    return {"Authorization": f"Bearer {token}"}


# ── Step 0: Login ──
def do_login():
    global token
    credentials_list = [
        {"phone": "13800138000", "password": "admin123"},
        {"phone": "13800000000", "password": "admin123"},
    ]
    for creds in credentials_list:
        try:
            r = requests.post(LOGIN_URL, json=creds, timeout=15)
            if r.status_code == 200:
                data = r.json()
                token = data.get("token")
                if token:
                    print(f"  Login OK with phone={creds['phone']}")
                    return True
        except Exception as e:
            print(f"  Login attempt failed for {creds['phone']}: {e}")
    return False


# ── TC-01: Unauthenticated access ──
def tc01():
    tc_id, name = "TC-01", "Unauthenticated access returns 401"
    try:
        r = requests.get(AI_CONFIG_URL, timeout=15)
        if r.status_code in (401, 403):
            record(tc_id, name, True)
        else:
            record(tc_id, name, False, f"Expected 401/403, got {r.status_code}: {r.text[:200]}")
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-02: Get AI config list ──
def tc02():
    tc_id, name = "TC-02", "Admin gets AI config list"
    try:
        r = requests.get(AI_CONFIG_URL, headers=get_auth_header(), timeout=15)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}: {r.text[:200]}")
            return
        data = r.json()
        if "items" not in data:
            record(tc_id, name, False, f"Response missing 'items' key. Got: {list(data.keys())}")
            return
        if not isinstance(data["items"], list):
            record(tc_id, name, False, f"'items' is not a list: {type(data['items'])}")
            return
        record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-03: Create AI config ──
def tc03():
    global created_config_id
    tc_id, name = "TC-03", "Admin creates AI config"
    payload = {
        "provider_name": "TestProvider",
        "base_url": "https://api.test.com/v1",
        "model_name": "test-model",
        "api_key": "sk-test123456789",
        "is_active": True,
        "max_tokens": 2048,
        "temperature": 0.5,
    }
    try:
        r = requests.post(AI_CONFIG_URL, json=payload, headers=get_auth_header(), timeout=15)
        if r.status_code not in (200, 201):
            record(tc_id, name, False, f"HTTP {r.status_code}: {r.text[:300]}")
            return
        data = r.json()
        required_fields = ["id", "provider_name", "base_url", "model_name", "is_active", "max_tokens", "temperature"]
        missing = [f for f in required_fields if f not in data]
        errors = []
        if missing:
            errors.append(f"Missing fields: {missing}. Got keys: {list(data.keys())}")
        if "id" not in data:
            record(tc_id, name, False, f"Response has no 'id' field, cannot proceed. Keys: {list(data.keys())}")
            return
        created_config_id = data["id"]
        if data.get("provider_name") != "TestProvider":
            errors.append(f"provider_name mismatch: {data.get('provider_name')}")
        if "max_tokens" in data and data["max_tokens"] != 2048:
            errors.append(f"max_tokens mismatch: {data['max_tokens']}")
        if "temperature" in data and data["temperature"] != 0.5:
            errors.append(f"temperature mismatch: {data['temperature']}")
        if errors:
            record(tc_id, name, False, "; ".join(errors))
        else:
            record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-04: Verify created config in list with masked api_key ──
def tc04():
    tc_id, name = "TC-04", "Created config in list with masked api_key"
    if created_config_id is None:
        record(tc_id, name, False, "Skipped: no config created in TC-03")
        return
    try:
        r = requests.get(AI_CONFIG_URL, headers=get_auth_header(), timeout=15)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}")
            return
        data = r.json()
        items = data.get("items", [])
        target = None
        for item in items:
            if item.get("id") == created_config_id:
                target = item
                break
        if not target:
            record(tc_id, name, False, f"Config id={created_config_id} not found in list of {len(items)} items")
            return
        api_key_val = target.get("api_key", "")
        if "****" not in str(api_key_val):
            record(tc_id, name, False, f"api_key not masked: '{api_key_val}'")
            return
        if api_key_val != "sk-test12****":
            record(tc_id, name, False, f"api_key mask mismatch: got '{api_key_val}', expected 'sk-test12****'")
            return
        record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-05: Update AI config ──
def tc05():
    tc_id, name = "TC-05", "Admin updates AI config"
    if created_config_id is None:
        record(tc_id, name, False, "Skipped: no config created in TC-03")
        return
    payload = {
        "model_name": "updated-model",
        "max_tokens": 8192,
        "temperature": 0.9,
    }
    try:
        r = requests.put(f"{AI_CONFIG_URL}/{created_config_id}", json=payload, headers=get_auth_header(), timeout=15)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}: {r.text[:300]}")
            return
        data = r.json()
        if data.get("model_name") != "updated-model":
            record(tc_id, name, False, f"model_name not updated: {data.get('model_name')}")
            return
        if data.get("max_tokens") != 8192:
            record(tc_id, name, False, f"max_tokens not updated: {data.get('max_tokens')}")
            return
        if data.get("temperature") != 0.9:
            record(tc_id, name, False, f"temperature not updated: {data.get('temperature')}")
            return
        record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-06: Verify updated values in list ──
def tc06():
    tc_id, name = "TC-06", "Verify updated values in list"
    if created_config_id is None:
        record(tc_id, name, False, "Skipped: no config created in TC-03")
        return
    try:
        r = requests.get(AI_CONFIG_URL, headers=get_auth_header(), timeout=15)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}")
            return
        items = r.json().get("items", [])
        target = None
        for item in items:
            if item.get("id") == created_config_id:
                target = item
                break
        if not target:
            record(tc_id, name, False, f"Config id={created_config_id} not found in list")
            return
        errors = []
        if target.get("model_name") != "updated-model":
            errors.append(f"model_name={target.get('model_name')}, expected 'updated-model'")
        if target.get("max_tokens") != 8192:
            errors.append(f"max_tokens={target.get('max_tokens')}, expected 8192")
        if target.get("temperature") != 0.9:
            errors.append(f"temperature={target.get('temperature')}, expected 0.9")
        if errors:
            record(tc_id, name, False, "; ".join(errors))
        else:
            record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-07: Test connection endpoint ──
def tc07():
    tc_id, name = "TC-07", "Test connection endpoint returns success+message"
    payload = {
        "provider_name": "TestProvider",
        "base_url": "https://api.test.com/v1",
        "model_name": "test-model",
        "api_key": "sk-fake",
    }
    try:
        r = requests.post(f"{AI_CONFIG_URL}/test", json=payload, headers=get_auth_header(), timeout=20)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}: {r.text[:300]}")
            return
        data = r.json()
        if "success" not in data:
            record(tc_id, name, False, f"Missing 'success' field. Got keys: {list(data.keys())}")
            return
        if not isinstance(data["success"], bool):
            record(tc_id, name, False, f"'success' is not boolean: {type(data['success'])}")
            return
        if "message" not in data:
            record(tc_id, name, False, f"Missing 'message' field. Got keys: {list(data.keys())}")
            return
        if not isinstance(data["message"], str):
            record(tc_id, name, False, f"'message' is not string: {type(data['message'])}")
            return
        record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-08: Delete AI config ──
def tc08():
    tc_id, name = "TC-08", "Admin deletes AI config"
    if created_config_id is None:
        record(tc_id, name, False, "Skipped: no config created in TC-03")
        return
    try:
        r = requests.delete(f"{AI_CONFIG_URL}/{created_config_id}", headers=get_auth_header(), timeout=15)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}: {r.text[:300]}")
            return
        record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-09: Verify deletion ──
def tc09():
    tc_id, name = "TC-09", "Deleted config not in list"
    if created_config_id is None:
        record(tc_id, name, False, "Skipped: no config created in TC-03")
        return
    try:
        r = requests.get(AI_CONFIG_URL, headers=get_auth_header(), timeout=15)
        if r.status_code != 200:
            record(tc_id, name, False, f"HTTP {r.status_code}")
            return
        items = r.json().get("items", [])
        found = any(item.get("id") == created_config_id for item in items)
        if found:
            record(tc_id, name, False, f"Config id={created_config_id} still in list after deletion")
        else:
            record(tc_id, name, True)
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── TC-10: Delete non-existent config ──
def tc10():
    tc_id, name = "TC-10", "Delete non-existent config returns 404"
    try:
        r = requests.delete(f"{AI_CONFIG_URL}/99999", headers=get_auth_header(), timeout=15)
        if r.status_code == 404:
            record(tc_id, name, True)
        else:
            record(tc_id, name, False, f"Expected 404, got {r.status_code}: {r.text[:200]}")
    except Exception as e:
        record(tc_id, name, False, str(e))


# ── Main ──
def main():
    print("=" * 60)
    print("AI Model Config CRUD - Server Integration Tests")
    print(f"Target: {BASE}")
    print("=" * 60)

    print("\n[Step 0] Admin Login")
    if not do_login():
        print("  FATAL: Cannot obtain admin token. Aborting.")
        sys.exit(1)

    print("\n[Running Test Cases]")
    tc01()
    tc02()
    tc03()
    tc04()
    tc05()
    tc06()
    tc07()
    tc08()
    tc09()
    tc10()

    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    print(f"TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}")
    print("=" * 60)

    if passed > 0:
        print("\nPassed:")
        for r in results:
            if r["passed"]:
                print(f"  [PASS] {r['id']}: {r['name']}")

    if failed > 0:
        print("\nFailed:")
        for r in results:
            if not r["passed"]:
                print(f"  [FAIL] {r['id']}: {r['name']}")
                if r["detail"]:
                    print(f"         Bug: {r['detail']}")

    print()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
