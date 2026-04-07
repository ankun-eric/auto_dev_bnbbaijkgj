import requests
import json
import sys
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE_URL}/api"


def main():
    passed = 0
    failed = 0
    errors = []

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f"  PASS: {msg}")

    def fail(msg):
        nonlocal failed
        failed += 1
        errors.append(msg)
        print(f"  FAIL: {msg}")

    # 1. Health check
    print("\nTC-000: Health check")
    try:
        r = requests.get(f"{API}/health", verify=False, timeout=10)
        if r.status_code == 200:
            ok("Health check returned 200")
        else:
            fail(f"Health check failed: status {r.status_code}")
    except Exception as e:
        fail(f"Health check exception: {e}")

    # 2. Admin login
    print("\nTC-000b: Admin login")
    token = None
    headers = {}
    try:
        r = requests.post(f"{API}/auth/login", json={"phone": "13800000000", "password": "admin123"}, verify=False, timeout=10)
        if r.status_code == 200:
            data = r.json()
            token = data.get("access_token") or data.get("token")
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                ok(f"Admin login succeeded, token obtained")
            else:
                fail(f"Login returned 200 but no token in response: {data}")
        else:
            fail(f"Login failed: status {r.status_code}, body: {r.text[:200]}")
    except Exception as e:
        fail(f"Login exception: {e}")

    if not token:
        print("\nCannot proceed without authentication token.")
        print(f"\nTotal: {passed} passed, {failed} failed")
        return 1

    # TC-001: Scene list has no legacy fields
    print("\nTC-001: Scene list - no legacy fields (ai_model_id, ocr_provider)")
    try:
        r = requests.get(f"{API}/admin/ocr/scenes", headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            scenes = r.json()
            if not isinstance(scenes, list):
                fail(f"Expected list, got {type(scenes).__name__}")
            else:
                legacy_found = False
                for s in scenes:
                    if "ai_model_id" in s:
                        fail(f"Legacy field ai_model_id found in scene: {s.get('scene_name')}")
                        legacy_found = True
                        break
                    if "ocr_provider" in s:
                        fail(f"Legacy field ocr_provider found in scene: {s.get('scene_name')}")
                        legacy_found = True
                        break
                if not legacy_found:
                    ok(f"Scene list OK ({len(scenes)} scenes, no legacy fields)")
                    has_prompt = all("prompt_content" in s for s in scenes)
                    if has_prompt:
                        ok("All scenes have prompt_content field")
                    else:
                        fail("Some scenes missing prompt_content field")
        else:
            fail(f"Get scenes failed: status {r.status_code}")
    except Exception as e:
        fail(f"Get scenes exception: {e}")

    # TC-002: Create scene with prompt_content
    print("\nTC-002: Create scene with prompt_content")
    created_id = None
    test_scene_name = f"test_scene_deploy_{int(time.time())}"
    try:
        r = requests.post(f"{API}/admin/ocr/scenes", json={
            "scene_name": test_scene_name,
            "prompt_content": "This is a test prompt for deployment verification."
        }, headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("scene_name") == test_scene_name and data.get("prompt_content"):
                created_id = data["id"]
                ok(f"Create scene succeeded (id={created_id})")
            else:
                fail(f"Create scene returned unexpected data: {data}")
        else:
            fail(f"Create scene failed: status {r.status_code}, body: {r.text[:200]}")
    except Exception as e:
        fail(f"Create scene exception: {e}")

    # TC-003: Duplicate name returns 400
    print("\nTC-003: Create scene - duplicate name returns 400")
    if created_id:
        try:
            r = requests.post(f"{API}/admin/ocr/scenes", json={
                "scene_name": test_scene_name,
                "prompt_content": "duplicate"
            }, headers=headers, verify=False, timeout=10)
            if r.status_code == 400:
                ok("Duplicate scene name correctly returns 400")
            else:
                fail(f"Expected 400 for duplicate name, got {r.status_code}")
        except Exception as e:
            fail(f"Duplicate name test exception: {e}")
    else:
        fail("Skipped: no created scene to test duplicate name")

    # TC-004: Update scene prompt_content
    print("\nTC-004: Update scene - modify prompt_content")
    if created_id:
        try:
            r = requests.put(f"{API}/admin/ocr/scenes/{created_id}", json={
                "prompt_content": "Updated prompt content for testing."
            }, headers=headers, verify=False, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("prompt_content") == "Updated prompt content for testing.":
                    ok("Update scene prompt_content succeeded")
                else:
                    fail(f"Update returned wrong prompt_content: {data.get('prompt_content')}")
            else:
                fail(f"Update scene failed: status {r.status_code}, body: {r.text[:200]}")
        except Exception as e:
            fail(f"Update scene exception: {e}")
    else:
        fail("Skipped: no created scene to update")

    # TC-005: Update non-existent scene returns 404
    print("\nTC-005: Update non-existent scene returns 404")
    try:
        r = requests.put(f"{API}/admin/ocr/scenes/99999", json={
            "scene_name": "nonexistent"
        }, headers=headers, verify=False, timeout=10)
        if r.status_code == 404:
            ok("Update non-existent scene correctly returns 404")
        else:
            fail(f"Expected 404, got {r.status_code}")
    except Exception as e:
        fail(f"Update non-existent exception: {e}")

    # TC-006: Delete custom scene
    print("\nTC-006: Delete custom scene")
    if created_id:
        try:
            r = requests.delete(f"{API}/admin/ocr/scenes/{created_id}", headers=headers, verify=False, timeout=10)
            if r.status_code == 200:
                ok("Delete custom scene succeeded")
            else:
                fail(f"Delete custom scene failed: status {r.status_code}, body: {r.text[:200]}")
        except Exception as e:
            fail(f"Delete custom scene exception: {e}")
    else:
        fail("Skipped: no created scene to delete")

    # TC-007: Delete preset scene returns 400
    print("\nTC-007: Delete preset scene returns 400")
    try:
        r = requests.get(f"{API}/admin/ocr/scenes", headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            preset_scenes = [s for s in r.json() if s.get("is_preset")]
            if preset_scenes:
                preset_id = preset_scenes[0]["id"]
                r = requests.delete(f"{API}/admin/ocr/scenes/{preset_id}", headers=headers, verify=False, timeout=10)
                if r.status_code == 400:
                    ok("Delete preset scene correctly returns 400")
                else:
                    fail(f"Expected 400 for preset delete, got {r.status_code}")
            else:
                print("  SKIP: No preset scenes found to test")
        else:
            fail(f"Get scenes for preset test failed: {r.status_code}")
    except Exception as e:
        fail(f"Delete preset exception: {e}")

    # TC-008: Delete non-existent scene returns 404
    print("\nTC-008: Delete non-existent scene returns 404")
    try:
        r = requests.delete(f"{API}/admin/ocr/scenes/99999", headers=headers, verify=False, timeout=10)
        if r.status_code == 404:
            ok("Delete non-existent scene correctly returns 404")
        else:
            fail(f"Expected 404, got {r.status_code}")
    except Exception as e:
        fail(f"Delete non-existent exception: {e}")

    # TC-009: Get upload limits
    print("\nTC-009: Get upload limits")
    try:
        r = requests.get(f"{API}/admin/ocr/upload-limits", headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "max_batch_count" in data and "max_file_size_mb" in data:
                ok(f"Get upload limits succeeded (batch={data['max_batch_count']}, size={data['max_file_size_mb']}MB)")
            else:
                fail(f"Upload limits missing expected fields: {data}")
        else:
            fail(f"Get upload limits failed: status {r.status_code}")
    except Exception as e:
        fail(f"Get upload limits exception: {e}")

    # TC-010: Update upload limits
    print("\nTC-010: Update upload limits")
    try:
        r = requests.put(f"{API}/admin/ocr/upload-limits", json={
            "max_batch_count": 8,
            "max_file_size_mb": 10
        }, headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("max_batch_count") == 8 and data.get("max_file_size_mb") == 10:
                ok("Update upload limits succeeded")
                # Restore defaults
                requests.put(f"{API}/admin/ocr/upload-limits", json={
                    "max_batch_count": 5, "max_file_size_mb": 5
                }, headers=headers, verify=False, timeout=10)
            else:
                fail(f"Update limits returned unexpected values: {data}")
        else:
            fail(f"Update upload limits failed: status {r.status_code}, body: {r.text[:200]}")
    except Exception as e:
        fail(f"Update upload limits exception: {e}")

    # TC-011: No auth returns 401/403
    print("\nTC-011: Unauthenticated access returns 401/403")
    no_auth_endpoints = [
        ("GET", f"{API}/admin/ocr/scenes"),
        ("POST", f"{API}/admin/ocr/scenes"),
        ("PUT", f"{API}/admin/ocr/scenes/1"),
        ("DELETE", f"{API}/admin/ocr/scenes/1"),
        ("GET", f"{API}/admin/ocr/upload-limits"),
        ("PUT", f"{API}/admin/ocr/upload-limits"),
    ]
    all_auth_ok = True
    for method, url in no_auth_endpoints:
        try:
            if method == "GET":
                r = requests.get(url, verify=False, timeout=10)
            elif method == "POST":
                r = requests.post(url, json={"scene_name": "x"}, verify=False, timeout=10)
            elif method == "PUT":
                r = requests.put(url, json={"scene_name": "x"}, verify=False, timeout=10)
            elif method == "DELETE":
                r = requests.delete(url, verify=False, timeout=10)
            if r.status_code not in (401, 403):
                fail(f"{method} {url.split('/api/')[-1]} without auth returned {r.status_code} (expected 401/403)")
                all_auth_ok = False
        except Exception as e:
            fail(f"{method} {url} exception: {e}")
            all_auth_ok = False
    if all_auth_ok:
        ok("All endpoints correctly require authentication (401/403)")

    # TC-012: Admin OCR global config page accessible
    print("\nTC-012: Admin OCR global config page accessible")
    try:
        r = requests.get(f"{BASE_URL}/admin/ocr-global-config", verify=False, allow_redirects=True, timeout=15)
        if r.status_code in (200, 302, 307):
            ok(f"Admin OCR global config page accessible (status {r.status_code})")
        else:
            fail(f"Admin page not accessible: status {r.status_code}")
    except Exception as e:
        fail(f"Admin page exception: {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    if errors:
        print(f"\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
