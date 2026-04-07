"""Server-side API tests for OCR Details feature."""
import json
import requests
import sys

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
RESULTS = []


def log(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    RESULTS.append((name, ok))
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))


def get_admin_token():
    resp = requests.post(f"{BASE}/admin/login", json={"phone": "13800000000", "password": "admin123"}, verify=False)
    if resp.status_code != 200:
        print(f"Admin login failed: {resp.status_code} {resp.text[:200]}")
        sys.exit(1)
    return resp.json()["token"]


def main():
    print("=" * 60)
    print("Server API Tests: OCR Details Feature")
    print("=" * 60)

    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    log("Admin login", True)

    # ---- Test 1: Health check ----
    r = requests.get(f"{BASE}/health", verify=False)
    log("API health check", r.status_code == 200, f"HTTP {r.status_code}")

    # ---- Test 2: Checkup statistics ----
    r = requests.get(f"{BASE}/admin/checkup-details/statistics", headers=headers, verify=False)
    log("Checkup statistics endpoint", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        log("Checkup stats has total field", "total" in data)
        log("Checkup stats has today_count field", "today_count" in data)
        log("Checkup stats has abnormal_count field", "abnormal_count" in data)
        log("Checkup stats has month_count field", "month_count" in data)

    # ---- Test 3: Checkup list ----
    r = requests.get(f"{BASE}/admin/checkup-details", headers=headers, params={"page": 1, "page_size": 10}, verify=False)
    log("Checkup list endpoint", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        log("Checkup list has items field", "items" in data)
        log("Checkup list has total field", "total" in data)
        log("Checkup list has page field", "page" in data)

    # ---- Test 4: Checkup list with filters ----
    r = requests.get(f"{BASE}/admin/checkup-details", headers=headers,
                     params={"status": "normal", "report_type": "血常规"}, verify=False)
    log("Checkup list with filters", r.status_code == 200, f"HTTP {r.status_code}")

    # ---- Test 5: Checkup detail 404 ----
    r = requests.get(f"{BASE}/admin/checkup-details/99999", headers=headers, verify=False)
    log("Checkup detail not found", r.status_code == 404)

    # ---- Test 6: Drug statistics ----
    r = requests.get(f"{BASE}/admin/drug-details/statistics", headers=headers, verify=False)
    log("Drug statistics endpoint", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        log("Drug stats has total field", "total" in data)
        log("Drug stats has today_count field", "today_count" in data)
        log("Drug stats has drug_types_count field", "drug_types_count" in data)
        log("Drug stats has month_count field", "month_count" in data)

    # ---- Test 7: Drug list ----
    r = requests.get(f"{BASE}/admin/drug-details", headers=headers, params={"page": 1, "page_size": 10}, verify=False)
    log("Drug list endpoint", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        log("Drug list has items field", "items" in data)
        log("Drug list has total field", "total" in data)

    # ---- Test 8: Drug list with filters ----
    r = requests.get(f"{BASE}/admin/drug-details", headers=headers,
                     params={"drug_name": "test", "drug_category": "处方药"}, verify=False)
    log("Drug list with filters", r.status_code == 200, f"HTTP {r.status_code}")

    # ---- Test 9: Drug detail 404 ----
    r = requests.get(f"{BASE}/admin/drug-details/99999", headers=headers, verify=False)
    log("Drug detail not found", r.status_code == 404)

    # ---- Test 10: Prompts include OCR types ----
    r = requests.get(f"{BASE}/admin/ai-center/prompts", headers=headers, verify=False)
    log("Prompts endpoint", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        items = data.get("items", data if isinstance(data, list) else [])
        chat_types = [i["chat_type"] for i in items]
        log("OCR checkup prompt exists", "ocr_checkup_report" in chat_types, str(chat_types))
        log("OCR drug prompt exists", "ocr_drug_identify" in chat_types, str(chat_types))

    # ---- Test 11: OCR scene templates no prompt_content ----
    r = requests.get(f"{BASE}/admin/ocr/scenes", headers=headers, verify=False)
    log("OCR scenes endpoint", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        scenes = r.json()
        if scenes:
            first = scenes[0] if isinstance(scenes, list) else scenes.get("items", [{}])[0]
            log("Scene template has no prompt_content", "prompt_content" not in first, str(list(first.keys())))

    # ---- Test 12: No auth should fail ----
    r = requests.get(f"{BASE}/admin/checkup-details/statistics", verify=False)
    log("Checkup stats unauthorized", r.status_code in (401, 403), f"HTTP {r.status_code}")

    r = requests.get(f"{BASE}/admin/drug-details/statistics", verify=False)
    log("Drug stats unauthorized", r.status_code in (401, 403), f"HTTP {r.status_code}")

    # ---- Test 13: Admin page accessible ----
    admin_url = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/"
    r = requests.get(admin_url, verify=False, allow_redirects=True)
    log("Admin page accessible", r.status_code == 200, f"HTTP {r.status_code}")

    # ---- Summary ----
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in RESULTS if ok)
    failed = sum(1 for _, ok in RESULTS if not ok)
    print(f"Total: {len(RESULTS)}, Passed: {passed}, Failed: {failed}")
    if failed:
        print("Failed tests:")
        for name, ok in RESULTS:
            if not ok:
                print(f"  - {name}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
