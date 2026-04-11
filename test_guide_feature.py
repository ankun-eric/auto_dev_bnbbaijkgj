#!/usr/bin/env python3
"""Test the new health guide feature (guide_count, guide-status APIs)."""

import random
import requests
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


def get_user_token(phone=None):
    """Register/login a user and return token."""
    if phone is None:
        phone = f"1{random.randint(3000000000, 9999999999)}"
    
    # Send SMS code
    resp = requests.post(f"{BASE_URL}/api/auth/sms-code", json={"phone": phone}, timeout=10)
    
    # Login with test code 123456
    resp = requests.post(f"{BASE_URL}/api/auth/sms-login",
                         json={"phone": phone, "code": "123456"}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token", "")
        return token, phone
    return "", phone


def test_health_endpoint():
    print("\n[1] Backend Health Check")
    resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
    check("GET /api/health returns 200", resp.status_code == 200, f"got {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        check("Health response has status field", "status" in data or "message" in data, str(data))


def test_guide_status_unauthenticated():
    print("\n[2] Guide Status - Unauthenticated Access")
    resp = requests.get(f"{BASE_URL}/api/health/guide-status", timeout=10)
    check("GET /api/health/guide-status without token returns 401",
          resp.status_code == 401, f"got {resp.status_code}")

    resp = requests.post(f"{BASE_URL}/api/health/guide-status",
                         json={"action": "complete"}, timeout=10)
    check("POST /api/health/guide-status without token returns 401",
          resp.status_code == 401, f"got {resp.status_code}")


def test_guide_status_new_user():
    print("\n[3] Guide Status - New User")
    token, phone = get_user_token()
    if not token:
        print(f"  SKIP  (could not get user token for {phone})")
        return None, None

    headers = {"Authorization": f"Bearer {token}"}

    # New user should have guide shown
    resp = requests.get(f"{BASE_URL}/api/health/guide-status", headers=headers, timeout=10)
    check("GET /api/health/guide-status returns 200",
          resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

    if resp.status_code == 200:
        data = resp.json()
        check("Response has 'should_show_guide' field", "should_show_guide" in data, str(data))
        check("Response has 'guide_count' field", "guide_count" in data, str(data))
        check("Response has 'profile_completeness' field", "profile_completeness" in data, str(data))
        check("New user should_show_guide is True",
              data.get("should_show_guide") == True,
              f"got {data.get('should_show_guide')}")
        check("New user guide_count is 0",
              data.get("guide_count") == 0,
              f"got {data.get('guide_count')}")
        check("New user profile_completeness is 0.0",
              data.get("profile_completeness") == 0.0,
              f"got {data.get('profile_completeness')}")

    return token, phone


def test_guide_status_update(token, phone):
    print("\n[4] Guide Status - Update (First Time)")
    if not token:
        print("  SKIP  (no token)")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # First update (complete/skip action)
    resp = requests.post(f"{BASE_URL}/api/health/guide-status",
                         json={"action": "complete"}, headers=headers, timeout=10)
    check("POST /api/health/guide-status (action=complete) returns 200",
          resp.status_code == 200, f"got {resp.status_code}: {resp.text[:300]}")

    if resp.status_code == 200:
        data = resp.json()
        check("Response has 'guide_count' field", "guide_count" in data, str(data))
        check("guide_count incremented to 1",
              data.get("guide_count") == 1,
              f"got {data.get('guide_count')}")

    # Check status after first update
    resp2 = requests.get(f"{BASE_URL}/api/health/guide-status", headers=headers, timeout=10)
    if resp2.status_code == 200:
        data2 = resp2.json()
        check("After 1st update: guide_count is 1",
              data2.get("guide_count") == 1,
              f"got {data2.get('guide_count')}")
        # Profile still incomplete, guide_count < 2, so should still show
        check("After 1st update: should_show_guide still True (profile incomplete)",
              data2.get("should_show_guide") == True,
              f"got {data2.get('should_show_guide')}")


def test_guide_status_second_update(token):
    print("\n[5] Guide Status - Update (Second Time)")
    if not token:
        print("  SKIP  (no token)")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Second update
    resp = requests.post(f"{BASE_URL}/api/health/guide-status",
                         json={"action": "skip"}, headers=headers, timeout=10)
    check("POST /api/health/guide-status (action=skip) returns 200",
          resp.status_code == 200, f"got {resp.status_code}: {resp.text[:300]}")

    if resp.status_code == 200:
        data = resp.json()
        check("guide_count incremented to 2",
              data.get("guide_count") == 2,
              f"got {data.get('guide_count')}")

    # Check status after second update - should no longer show guide
    resp2 = requests.get(f"{BASE_URL}/api/health/guide-status", headers=headers, timeout=10)
    if resp2.status_code == 200:
        data2 = resp2.json()
        check("After 2nd update: guide_count is 2",
              data2.get("guide_count") == 2,
              f"got {data2.get('guide_count')}")
        check("After 2nd update: should_show_guide is False (guide_count >= 2)",
              data2.get("should_show_guide") == False,
              f"got {data2.get('should_show_guide')}")


def test_health_guide_page():
    print("\n[6] Health Guide Page Accessibility")
    resp = requests.get(f"{BASE_URL}/health-guide", timeout=15, allow_redirects=True)
    check("Health guide page accessible",
          resp.status_code in [200, 301, 302, 308],
          f"got {resp.status_code}")

    resp2 = requests.get(f"{BASE_URL}/health-profile", timeout=15, allow_redirects=True)
    check("Health profile page accessible",
          resp2.status_code in [200, 301, 302, 308],
          f"got {resp2.status_code}")


def test_login_page():
    print("\n[7] Login Page")
    resp = requests.get(f"{BASE_URL}/login", timeout=15, allow_redirects=True)
    check("Login page accessible",
          resp.status_code in [200, 301, 302, 308],
          f"got {resp.status_code}")


if __name__ == "__main__":
    print("=" * 60)
    print("Health Guide Feature - Server Tests")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    test_health_endpoint()
    test_guide_status_unauthenticated()
    token, phone = test_guide_status_new_user()
    test_guide_status_update(token, phone)
    test_guide_status_second_update(token)
    test_health_guide_page()
    test_login_page()

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    for r in results:
        print(r)
    print(f"\nTotal: {PASS + FAIL} | PASS: {PASS} | FAIL: {FAIL}")

    sys.exit(0 if FAIL == 0 else 1)
