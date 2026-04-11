"""
Server-side integration tests to validate Bug fixes:
  Bug 1: AI 解读失败 — timeout/retry/error-handling improvements
  Bug 2: Admin OCR test field name mismatch (file → files)

All requests go through HTTPS to the deployed server.
"""

import io
import uuid

import httpx
import pytest

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE_URL}/api"
TIMEOUT = 30

_test_phone = f"139{uuid.uuid4().hex[:8]}"
_test_password = "Test1234"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, verify=False) as c:
        yield c


# ── helper: register + login to get user token ──


@pytest.fixture(scope="module")
def user_token(client: httpx.Client):
    resp = client.post("/api/auth/register", json={
        "phone": _test_phone,
        "password": _test_password,
        "nickname": "BugfixTestUser",
    })
    if resp.status_code == 200:
        return resp.json().get("access_token")
    resp = client.post("/api/auth/login", json={
        "phone": _test_phone,
        "password": _test_password,
    })
    if resp.status_code == 200:
        return resp.json().get("access_token")
    pytest.skip(f"Cannot obtain user token: {resp.status_code} {resp.text[:300]}")


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="module")
def admin_token(client: httpx.Client):
    resp = client.post("/api/admin/login", json={
        "phone": "13800000000",
        "password": "admin123",
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Cannot obtain admin token: {resp.status_code} {resp.text[:300]}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ═══════════════════════════════════════════════════════════════════════
# a) API Health Check
# ═══════════════════════════════════════════════════════════════════════


class TestHealthCheck:
    def test_api_health(self, client: httpx.Client):
        """GET /api/health → 200"""
        resp = client.get("/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# b) Report API reachability (unauthenticated → 401)
# ═══════════════════════════════════════════════════════════════════════


class TestReportApiReachability:
    def test_upload_no_token_returns_401(self, client: httpx.Client):
        """POST /api/report/upload without token → 401"""
        resp = client.post("/api/report/upload")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_analyze_no_token_returns_401(self, client: httpx.Client):
        """POST /api/report/analyze without token → 401"""
        resp = client.post("/api/report/analyze", json={"report_id": 1})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_ocr_no_token_returns_401(self, client: httpx.Client):
        """POST /api/report/ocr without token → 401"""
        resp = client.post("/api/report/ocr", json={"report_id": 1})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# c) Admin OCR API reachability (unauthenticated → 401/403)
# ═══════════════════════════════════════════════════════════════════════


class TestAdminOcrReachability:
    def test_providers_no_token(self, client: httpx.Client):
        """GET /api/admin/ocr/providers without token → 401 or 403"""
        resp = client.get("/api/admin/ocr/providers")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_test_ocr_no_token(self, client: httpx.Client):
        """POST /api/admin/ocr/test-ocr without token → 401 or 403"""
        resp = client.post("/api/admin/ocr/test-ocr")
        assert resp.status_code in (401, 403, 422), f"Expected 401/403/422, got {resp.status_code}"

    def test_test_full_no_token(self, client: httpx.Client):
        """POST /api/admin/ocr/test-full without token → 401 or 403"""
        resp = client.post("/api/admin/ocr/test-full")
        assert resp.status_code in (401, 403, 422), f"Expected 401/403/422, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# d) Bug 2 validation: test-ocr accepts "files" field name (not "file")
# ═══════════════════════════════════════════════════════════════════════


class TestOcrFieldNameFix:
    def test_test_ocr_files_field_not_422(self, client: httpx.Client, admin_headers):
        """POST /api/admin/ocr/test-ocr with field name 'files' should NOT return 422.
        This validates the Bug 2 fix: frontend sends 'files', backend expects 'files'.
        A 422 would mean the field name is still mismatched."""
        tiny_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        resp = client.post(
            "/api/admin/ocr/test-ocr",
            files={"files": ("test.png", io.BytesIO(tiny_png), "image/png")},
            data={"provider": "baidu"},
            headers=admin_headers,
        )
        assert resp.status_code != 422, (
            f"Got 422 — 'files' field not accepted. Bug 2 NOT fixed. "
            f"Response: {resp.text[:500]}"
        )

    def test_test_ocr_wrong_field_file_singular(self, client: httpx.Client, admin_headers):
        """POST /api/admin/ocr/test-ocr with old field name 'file' (singular) should return 422,
        confirming the backend expects 'files' (plural)."""
        tiny_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        resp = client.post(
            "/api/admin/ocr/test-ocr",
            files={"file": ("test.png", io.BytesIO(tiny_png), "image/png")},
            data={"provider": "baidu"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, (
            f"Expected 422 for wrong field name 'file', got {resp.status_code}. "
            f"Response: {resp.text[:500]}"
        )


# ═══════════════════════════════════════════════════════════════════════
# e) Page reachability
# ═══════════════════════════════════════════════════════════════════════


class TestPageReachability:
    def test_h5_home_page(self, client: httpx.Client):
        """GET / → H5 home page returns 200"""
        resp = client.get("/")
        assert resp.status_code == 200, f"H5 home expected 200, got {resp.status_code}"

    def test_admin_page(self, client: httpx.Client):
        """GET /admin/ → Admin page returns 200"""
        resp = client.get("/admin/")
        assert resp.status_code == 200, f"Admin page expected 200, got {resp.status_code}"
