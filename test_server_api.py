"""
Server-side API tests for bini-health new features.
Tests against the live deployed server.
"""
import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Optional

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
USER_PHONE = "13900000001"
USER_PASSWORD = "User123456"

_admin_token: Optional[str] = None
_user_token: Optional[str] = None

RESULTS: list[dict] = []
PASS = 0
FAIL = 0


def req(
    method: str,
    path: str,
    body: Any = None,
    token: Optional[str] = None,
    expected_status: int = 200,
    test_name: str = "",
) -> tuple[int, Any]:
    url = BASE_URL + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(request, context=CTX, timeout=20)
        code = resp.status
        try:
            resp_data = json.loads(resp.read().decode())
        except Exception:
            resp_data = {}
        return code, resp_data
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            resp_data = json.loads(e.read().decode())
        except Exception:
            resp_data = {}
        return code, resp_data
    except Exception as e:
        return 0, {"error": str(e)}


def check(test_name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    icon = "✓" if condition else "✗"
    print(f"  [{icon}] {test_name}" + (f" | {detail}" if detail else ""))
    RESULTS.append({"name": test_name, "passed": condition, "detail": detail})


def get_admin_token() -> Optional[str]:
    global _admin_token
    if _admin_token:
        return _admin_token
    # Try admin login
    code, data = req("POST", "/api/admin/auth/login",
                     body={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    if code != 200:
        code, data = req("POST", "/api/auth/login",
                         body={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    if code == 200 and "access_token" in data:
        _admin_token = data["access_token"]
    elif code == 200 and "token" in data:
        _admin_token = data["token"]
    return _admin_token


def get_user_token() -> Optional[str]:
    global _user_token
    if _user_token:
        return _user_token
    # Register then login
    req("POST", "/api/auth/register",
        body={"phone": USER_PHONE, "password": USER_PASSWORD, "nickname": "TestUser"})
    code, data = req("POST", "/api/auth/login",
                     body={"phone": USER_PHONE, "password": USER_PASSWORD})
    if code == 200:
        _user_token = data.get("access_token") or data.get("token")
    return _user_token


print("=" * 70)
print("bini-health Server API Tests")
print(f"Target: {BASE_URL}")
print("=" * 70)

# ─── Health Check ───
print("\n[Health Check]")
code, data = req("GET", "/api/health")
check("GET /api/health returns 200", code == 200, f"status={code}")
check("health response has status field", "status" in data, f"data={data}")

# ─── Admin Login ───
print("\n[Admin Authentication]")
admin_token = get_admin_token()
check("Admin login success", admin_token is not None, f"token={'yes' if admin_token else 'no'}")

# ─── Prompt Templates API ───
print("\n[Prompt Templates API]")

# List all templates
code, data = req("GET", "/api/admin/prompt-templates", token=admin_token)
check("GET /api/admin/prompt-templates returns 200", code == 200, f"status={code}")
if code == 200:
    check("prompt-templates returns list", isinstance(data, list), f"type={type(data).__name__}")
    if data:
        first = data[0]
        check("template has prompt_type field", "prompt_type" in first, str(first.keys()))
        check("template has display_name field", "display_name" in first, str(first.keys()))

# Get checkup_report template
code, data = req("GET", "/api/admin/prompt-templates/checkup_report", token=admin_token)
check("GET /api/admin/prompt-templates/checkup_report returns 200", code == 200, f"status={code}")
if code == 200:
    check("checkup_report template has prompt_type", data.get("prompt_type") == "checkup_report",
          f"prompt_type={data.get('prompt_type')}")
    check("checkup_report template has display_name", "display_name" in data,
          f"display_name={data.get('display_name')}")
    check("checkup_report template has history field", "history" in data, str(data.keys()))

# Get drug_general template
code, data = req("GET", "/api/admin/prompt-templates/drug_general", token=admin_token)
check("GET /api/admin/prompt-templates/drug_general returns 200", code == 200, f"status={code}")
if code == 200:
    check("drug_general template has correct prompt_type",
          data.get("prompt_type") == "drug_general", f"prompt_type={data.get('prompt_type')}")

# Update template (create new version)
code, data = req("PUT", "/api/admin/prompt-templates/checkup_report",
                 body={"content": f"测试Prompt内容 - updated at {int(time.time())}"},
                 token=admin_token)
check("PUT /api/admin/prompt-templates/checkup_report returns 200", code == 200, f"status={code}")
if code == 200:
    check("updated template has version field", "version" in data, str(data.keys()))
    check("updated template has is_active=True", data.get("is_active") is True,
          f"is_active={data.get('is_active')}")

# Invalid prompt type
code, data = req("GET", "/api/admin/prompt-templates/invalid_type_xyz", token=admin_token)
check("GET /api/admin/prompt-templates/invalid_type returns 400", code == 400, f"status={code}")

# Unauthorized - no token
code, data = req("GET", "/api/admin/prompt-templates")
check("GET /api/admin/prompt-templates without token returns 401", code == 401, f"status={code}")

# User token (non-admin) should get 403
user_token = get_user_token()
if user_token:
    code, data = req("GET", "/api/admin/prompt-templates", token=user_token)
    check("GET /api/admin/prompt-templates with user token returns 403", code == 403, f"status={code}")

# ─── Report Share API ───
print("\n[Report Share API]")

# Test share for non-existent token (should 404)
code, data = req("GET", "/api/report/share/nonexistent_token_xyz_abc_12345")
check("GET /api/report/share/nonexistent_token returns 404", code == 404, f"status={code}")

# Test creating share for non-existent report (needs auth)
if user_token:
    code, data = req("POST", "/api/report/share",
                     body={"report_id": 99999}, token=user_token)
    check("POST /api/report/share for nonexistent report returns 404", code == 404, f"status={code}")

# Unauthorized share creation
code, data = req("POST", "/api/report/share", body={"report_id": 1})
check("POST /api/report/share without token returns 401", code == 401, f"status={code}")

# ─── Drug Identify Share API ───
print("\n[Drug Identify Share API]")

# Test share for non-existent token (should 404)
code, data = req("GET", "/api/drug-identify/share/nonexistent_token_xyz_abc_12345")
check("GET /api/drug-identify/share/nonexistent_token returns 404", code == 404, f"status={code}")

# Unauthorized drug share creation
code, data = req("POST", "/api/drug-identify/1/share")
check("POST /api/drug-identify/{id}/share without token returns 401", code == 401, f"status={code}")

# Personal suggestion unauthorized
code, data = req("GET", "/api/drug-identify/1/personal-suggestion")
check("GET /api/drug-identify/{id}/personal-suggestion without token returns 401",
      code == 401, f"status={code}")

# Personal suggestion for non-existent record
if user_token:
    code, data = req("GET", "/api/drug-identify/99999/personal-suggestion", token=user_token)
    check("GET /api/drug-identify/99999/personal-suggestion returns 404", code == 404, f"status={code}")

    # Drug share for non-existent record
    code, data = req("POST", "/api/drug-identify/99999/share", token=user_token)
    check("POST /api/drug-identify/99999/share returns 404", code == 404, f"status={code}")

# ─── OCR Details (existing) ───
print("\n[OCR Details API]")
code, data = req("GET", "/api/admin/checkup-details/statistics", token=admin_token)
check("GET /api/admin/checkup-details/statistics returns 200", code == 200, f"status={code}")

code, data = req("GET", "/api/admin/drug-details/statistics", token=admin_token)
check("GET /api/admin/drug-details/statistics returns 200", code == 200, f"status={data}")

# ─── H5 Pages ───
print("\n[H5 Frontend]")
code, data = req("GET", "/")
check("H5 homepage accessible (200)", code == 200, f"status={code}")

# ─── Summary ───
print("\n" + "=" * 70)
print(f"TEST RESULTS: {PASS} PASSED, {FAIL} FAILED")
print("=" * 70)

if FAIL > 0:
    print("\nFAILED TESTS:")
    for r in RESULTS:
        if not r["passed"]:
            print(f"  ✗ {r['name']}: {r['detail']}")

print(f"\nPass rate: {PASS}/{PASS+FAIL} = {100*PASS//(PASS+FAIL) if (PASS+FAIL) > 0 else 0}%")
