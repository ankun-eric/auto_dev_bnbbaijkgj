#!/usr/bin/env python3
"""
Automated tests for home-menus API with Emoji icon support.
Tests the backend API endpoints that support the new Emoji icon recommendation feature.
"""
import requests
import json
import sys

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

session = requests.Session()
session.verify = True

results = {"passed": [], "failed": []}


def log_pass(name):
    print(f"  [PASS] {name}")
    results["passed"].append(name)


def log_fail(name, reason):
    print(f"  [FAIL] {name}: {reason}")
    results["failed"].append({"test": name, "reason": reason})


def get_admin_token():
    """Login and get admin token."""
    print("\n--- Login as admin ---")
    # Try admin login endpoint first
    resp = session.post(f"{API_URL}/admin/login", json={
        "phone": "13800000000",
        "password": "admin123"
    }, timeout=30)
    
    if resp.status_code != 200:
        # Try auth login
        resp = session.post(f"{API_URL}/auth/login", json={
            "phone": "13800000000",
            "password": "admin123"
        }, timeout=30)
    
    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code} {resp.text[:200]}")
        return None
    
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"Login successful, token: {token[:30]}...")
        return token
    else:
        print(f"No token in response: {data}")
        return None


def test_get_home_menus():
    """Test 1: GET /api/admin/home-menus - Get menu list."""
    print("\n--- Test 1: GET home-menus ---")
    resp = session.get(f"{API_URL}/admin/home-menus", timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            log_pass("GET /api/admin/home-menus returns list")
            print(f"  Found {len(data)} menus")
            if data:
                print(f"  First menu: {data[0]}")
            return data
        elif isinstance(data, dict) and ("items" in data or "data" in data):
            items = data.get("items", data.get("data", []))
            log_pass("GET /api/admin/home-menus returns paginated list")
            print(f"  Found {len(items)} menus")
            return items
        else:
            log_pass(f"GET /api/admin/home-menus returns 200 with data")
            return data if isinstance(data, list) else []
    else:
        log_fail("GET /api/admin/home-menus", f"Status {resp.status_code}: {resp.text[:200]}")
        return []


def test_create_menu_with_emoji():
    """Test 2: POST /api/admin/home-menus - Create menu with Emoji icon."""
    print("\n--- Test 2: POST home-menus with Emoji icon ---")
    
    test_menus = [
        {"emoji": "🏥", "name": "医疗健康_test_emoji"},
        {"emoji": "💊", "name": "药品管理_test_emoji"},
        {"emoji": "🩺", "name": "诊断服务_test_emoji"},
    ]
    
    created_ids = []
    for menu_data in test_menus:
        emoji = menu_data["emoji"]
        payload = {
            "name": menu_data["name"],
            "icon_type": "emoji",
            "icon_content": emoji,
            "link_type": "internal",
            "link_url": f"/test/emoji",
            "sort_order": 99,
            "is_visible": True,
        }
        
        resp = session.post(f"{API_URL}/admin/home-menus", json=payload, timeout=30)
        
        if resp.status_code in (200, 201):
            data = resp.json()
            menu_id = data.get("id")
            returned_emoji = data.get("icon_content", "")
            
            if returned_emoji == emoji:
                log_pass(f"POST with Emoji {emoji} - icon_content stored correctly")
            else:
                log_fail(f"POST with Emoji {emoji}", 
                        f"icon_content mismatch: expected '{emoji}', got '{returned_emoji}'")
            
            if menu_id:
                created_ids.append(menu_id)
                print(f"  Created menu id={menu_id}, icon_content='{returned_emoji}'")
        else:
            log_fail(f"POST with Emoji {emoji}", f"Status {resp.status_code}: {resp.text[:300]}")
    
    return created_ids


def test_get_menu_verify_emoji(menu_ids):
    """Test 3: Verify Emoji persisted in GET after POST."""
    print("\n--- Test 3: Verify Emoji persistence in GET ---")
    
    if not menu_ids:
        log_fail("Verify Emoji persistence", "No menu IDs to verify")
        return
    
    # Get all menus and check our created ones
    resp = session.get(f"{API_URL}/admin/home-menus", timeout=30)
    if resp.status_code != 200:
        log_fail("Verify Emoji persistence - GET", f"Status {resp.status_code}")
        return
    
    data = resp.json()
    menus_list = data if isinstance(data, list) else data.get("items", data.get("data", []))
    
    found = 0
    for menu in menus_list:
        if menu.get("id") in menu_ids:
            icon_content = menu.get("icon_content", "")
            if icon_content and len(icon_content) > 0:
                # Check if it's an emoji character (multi-byte)
                is_emoji = len(icon_content.encode("utf-8")) > len(icon_content)
                if is_emoji or any(ord(c) > 127 for c in icon_content):
                    log_pass(f"Emoji '{icon_content}' persisted correctly for menu id={menu.get('id')}")
                    found += 1
                else:
                    log_fail(f"Emoji persistence id={menu.get('id')}", 
                            f"icon_content '{icon_content}' doesn't appear to be emoji")
    
    if found == 0 and menu_ids:
        log_fail("Verify Emoji persistence", "Created menus not found in GET response")


def test_update_menu_with_emoji(menu_ids):
    """Test 4: PUT /api/admin/home-menus/{id} - Update menu with Emoji."""
    print("\n--- Test 4: PUT home-menus with Emoji update ---")
    
    if not menu_ids:
        log_fail("PUT with Emoji", "No menu IDs available")
        return
    
    menu_id = menu_ids[0]
    new_emoji = "🌟"
    
    payload = {
        "icon_content": new_emoji,
        "icon_type": "emoji",
    }
    
    resp = session.put(f"{API_URL}/admin/home-menus/{menu_id}", json=payload, timeout=30)
    
    if resp.status_code in (200, 201, 204):
        if resp.status_code == 204 or not resp.content:
            log_pass(f"PUT /api/admin/home-menus/{menu_id} with Emoji {new_emoji} - 204 No Content")
        else:
            data = resp.json()
            returned_emoji = data.get("icon_content", "")
            if returned_emoji == new_emoji:
                log_pass(f"PUT with Emoji {new_emoji} - updated correctly")
            else:
                log_fail(f"PUT with Emoji {new_emoji}", 
                        f"icon_content mismatch: expected '{new_emoji}', got '{returned_emoji}'")
    else:
        log_fail(f"PUT /api/admin/home-menus/{menu_id}", f"Status {resp.status_code}: {resp.text[:300]}")


def test_delete_menus(menu_ids):
    """Test 5: DELETE /api/admin/home-menus/{id} - Delete test menus."""
    print("\n--- Test 5: DELETE test menus ---")
    
    if not menu_ids:
        log_fail("DELETE menus", "No menu IDs to delete")
        return
    
    for menu_id in menu_ids:
        resp = session.delete(f"{API_URL}/admin/home-menus/{menu_id}", timeout=30)
        
        if resp.status_code in (200, 204):
            log_pass(f"DELETE /api/admin/home-menus/{menu_id}")
        else:
            log_fail(f"DELETE /api/admin/home-menus/{menu_id}", 
                    f"Status {resp.status_code}: {resp.text[:200]}")


def test_emoji_charset_compatibility():
    """Test 6: Verify emoji charset compatibility in database."""
    print("\n--- Test 6: Emoji charset compatibility ---")
    
    # Test various emoji characters
    emoji_chars = ["🏥", "💊", "🌟", "❤️", "🧬", "🔬", "🩺", "💉", "🏃", "🥗"]
    
    created_id = None
    for emoji in emoji_chars:
        payload = {
            "name": f"emoji_compat_test",
            "icon_type": "emoji",
            "icon_content": emoji,
            "link_type": "internal",
            "link_url": "/test/emoji",
            "sort_order": 999,
            "is_visible": True,
        }
        
        resp = session.post(f"{API_URL}/admin/home-menus", json=payload, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            returned = data.get("icon_content", "")
            if returned == emoji:
                log_pass(f"Emoji '{emoji}' (U+{ord(emoji[0]):04X}) stored and returned correctly")
            else:
                log_fail(f"Emoji charset {emoji}", f"Got '{returned}' instead of '{emoji}'")
            
            # Save one ID for cleanup
            if not created_id and data.get("id"):
                created_id = data.get("id")
            
            # Cleanup immediately
            menu_id = data.get("id")
            if menu_id:
                session.delete(f"{API_URL}/admin/home-menus/{menu_id}", timeout=10)
        else:
            log_fail(f"Emoji charset {emoji}", f"Create failed: {resp.status_code}")


def test_admin_frontend_accessible():
    """Test 7: Verify admin frontend is accessible."""
    print("\n--- Test 7: Admin frontend accessibility ---")
    
    resp = requests.get(f"{BASE_URL}/admin/", timeout=30, verify=True)
    if resp.status_code == 200 and len(resp.content) > 1000:
        log_pass(f"Admin frontend accessible (status={resp.status_code}, size={len(resp.content)} bytes)")
    else:
        log_fail("Admin frontend accessible", f"Status {resp.status_code}, size={len(resp.content)}")
    
    # Check for home-menus page specifically
    resp2 = requests.get(f"{BASE_URL}/admin/home-menus", timeout=30, verify=True)
    if resp2.status_code == 200:
        log_pass(f"Home-menus page accessible (status={resp2.status_code})")
    else:
        log_fail("Home-menus page accessible", f"Status {resp2.status_code}")


def main():
    print("=" * 60)
    print("Home Menus Emoji Feature - Automated Tests")
    print(f"API: {API_URL}")
    print("=" * 60)
    
    # Login
    token = get_admin_token()
    if not token:
        print("\nFATAL: Cannot login, aborting tests")
        sys.exit(1)
    
    # Run tests
    test_admin_frontend_accessible()
    existing_menus = test_get_home_menus()
    created_ids = test_create_menu_with_emoji()
    test_get_menu_verify_emoji(created_ids)
    test_update_menu_with_emoji(created_ids)
    test_delete_menus(created_ids)
    test_emoji_charset_compatibility()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"PASSED: {len(results['passed'])}")
    print(f"FAILED: {len(results['failed'])}")
    
    if results["failed"]:
        print("\nFailed tests:")
        for f in results["failed"]:
            print(f"  - {f['test']}: {f['reason']}")
    
    print("\nPassed tests:")
    for p in results["passed"]:
        print(f"  + {p}")
    
    return 0 if not results["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
