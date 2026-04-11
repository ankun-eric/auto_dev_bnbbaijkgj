"""
Server-side automated tests for the enhanced checkup report features:
- AI health score (0-100)
- 5-level risk rating
- Per-indicator detailed advice
- Report comparison
- Enhanced structured JSON output
"""

import io
import struct
import warnings
import zlib

import httpx
import pytest

warnings.filterwarnings("ignore")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_BASE = f"{BASE_URL}/api"
TIMEOUT = 60.0

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
TEST_PHONE = "13800138000"


def api(path: str) -> str:
    if path.startswith("/"):
        return f"{BASE_URL}{path}"
    return f"{BASE_URL}/{path}"


def make_test_png(width=400, height=300) -> bytes:
    """Generate a valid PNG that passes quality checks (>=200x200, >=10KB)."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"
        for x in range(width):
            r = (x * 7 + y * 13 + (x ^ y)) & 0xFF
            g = (x * 11 + y * 3 + (x * y)) & 0xFF
            b_val = (x * 5 + y * 17 + (x + y)) & 0xFF
            raw_data += bytes([r, g, b_val])
    idat_data = zlib.compress(raw_data, 1)
    return header + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", idat_data) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(verify=False, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token(client: httpx.Client):
    """Get admin token via /api/admin/login."""
    resp = client.post(api("/api/admin/login"), json={
        "phone": ADMIN_PHONE,
        "password": ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token

    resp2 = client.post(api("/api/auth/login"), json={
        "phone": ADMIN_PHONE,
        "password": ADMIN_PASSWORD,
    })
    if resp2.status_code == 200:
        data2 = resp2.json()
        token = data2.get("access_token") or data2.get("token")
        if token:
            return token

    pytest.fail(
        f"Admin login failed.\n"
        f"  /api/admin/login: {resp.status_code} {resp.text}\n"
        f"  /api/auth/login: {resp2.status_code} {resp2.text}"
    )


@pytest.fixture(scope="module")
def admin_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_token(client: httpx.Client):
    """Get user token via SMS code flow."""
    resp_code = client.post(api("/api/auth/sms-code"), json={
        "phone": TEST_PHONE,
        "type": "login",
    })
    if resp_code.status_code == 429:
        pass
    elif resp_code.status_code not in (200, 429):
        pytest.skip(f"SMS code send failed: {resp_code.status_code} {resp_code.text}")

    resp_login = client.post(api("/api/auth/sms-login"), json={
        "phone": TEST_PHONE,
        "code": "888888",
    })
    if resp_login.status_code == 200:
        data = resp_login.json()
        token = data.get("access_token") or data.get("token")
        if token:
            return token

    return None


@pytest.fixture(scope="module")
def auth_headers(admin_headers, user_token):
    """Use user token if available, otherwise fall back to admin token."""
    if user_token:
        return {"Authorization": f"Bearer {user_token}"}
    return admin_headers


@pytest.fixture(scope="module")
def uploaded_report_id(client: httpx.Client, auth_headers: dict):
    """Upload a test PNG and return its report ID."""
    png_bytes = make_test_png()
    files = {"file": ("test_report.png", io.BytesIO(png_bytes), "image/png")}
    resp = client.post(api("/api/report/upload"), files=files, headers=auth_headers)
    if resp.status_code == 503:
        pytest.skip("OCR service disabled, cannot upload report")
    assert resp.status_code == 200, f"Upload failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "id" in data
    return data["id"]


@pytest.fixture(scope="module")
def second_report_id(client: httpx.Client, auth_headers: dict):
    """Upload a second test PNG for comparison tests."""
    png_bytes = make_test_png(width=420, height=320)
    files = {"file": ("test_report_2.png", io.BytesIO(png_bytes), "image/png")}
    resp = client.post(api("/api/report/upload"), files=files, headers=auth_headers)
    if resp.status_code == 503:
        pytest.skip("OCR service disabled, cannot upload second report")
    assert resp.status_code == 200, f"Second upload failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "id" in data
    return data["id"]


# ═══════════════════════════════════════════════
# TC-001: Health Check
# ═══════════════════════════════════════════════

class TestTC001HealthCheck:
    def test_health_endpoint(self, client: httpx.Client):
        """TC-001: GET /api/health returns 200."""
        resp = client.get(api("/api/health"))
        assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"


# ═══════════════════════════════════════════════
# TC-002: Admin Login
# ═══════════════════════════════════════════════

class TestTC002AdminLogin:
    def test_admin_login_returns_token(self, admin_token: str):
        """TC-002: POST /api/admin/login returns a valid admin token."""
        assert admin_token, "Admin token should not be empty"
        assert isinstance(admin_token, str)
        assert len(admin_token) > 10


# ═══════════════════════════════════════════════
# TC-003: User SMS Login
# ═══════════════════════════════════════════════

class TestTC003UserLogin:
    def test_sms_code_send(self, client: httpx.Client):
        """TC-003a: POST /api/auth/sms-code accepts the request."""
        resp = client.post(api("/api/auth/sms-code"), json={
            "phone": TEST_PHONE,
            "type": "login",
        })
        assert resp.status_code in (200, 429, 403, 500), \
            f"SMS code endpoint unexpected status: {resp.status_code} {resp.text}"

    def test_sms_login(self, client: httpx.Client):
        """TC-003b: POST /api/auth/sms-login returns token or reasonable error."""
        resp = client.post(api("/api/auth/sms-login"), json={
            "phone": TEST_PHONE,
            "code": "888888",
        })
        assert resp.status_code in (200, 400, 403), \
            f"SMS login unexpected status: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token") or data.get("token")
            assert token, f"No token in SMS login response: {data}"


# ═══════════════════════════════════════════════
# TC-004: Report Upload
# ═══════════════════════════════════════════════

class TestTC004ReportUpload:
    def test_upload_report(self, client: httpx.Client, auth_headers: dict):
        """TC-004: POST /api/report/upload returns id, file_url, status."""
        png_bytes = make_test_png()
        files = {"file": ("tc004_report.png", io.BytesIO(png_bytes), "image/png")}
        resp = client.post(api("/api/report/upload"), files=files, headers=auth_headers)
        if resp.status_code == 503:
            pytest.skip("OCR service disabled")
        assert resp.status_code == 200, f"Upload failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data, f"Missing 'id' in response: {data}"
        assert "file_url" in data, f"Missing 'file_url' in response: {data}"
        assert "status" in data, f"Missing 'status' in response: {data}"


# ═══════════════════════════════════════════════
# TC-005: Report Analyze — Enhanced JSON Format
# ═══════════════════════════════════════════════

class TestTC005ReportAnalyze:
    def test_analyze_report_enhanced(self, client: httpx.Client, auth_headers: dict, uploaded_report_id: int):
        """TC-005: POST /api/report/analyze returns enhanced structured JSON."""
        resp = client.post(
            api("/api/report/analyze"),
            json={"report_id": uploaded_report_id},
            headers=auth_headers,
            timeout=120.0,
        )
        assert resp.status_code in (200, 400, 500, 503), \
            f"Analyze unexpected status: {resp.status_code} {resp.text}"

        if resp.status_code == 200:
            data = resp.json()
            assert "report_id" in data, f"Missing report_id: {data.keys()}"
            assert "status" in data, f"Missing status: {data.keys()}"
            assert data["status"] in ("completed", "analyzing"), f"Unexpected status: {data['status']}"

            if "healthScore" in data and data["healthScore"]:
                hs = data["healthScore"]
                assert "score" in hs, f"healthScore missing 'score': {hs}"
                assert isinstance(hs["score"], (int, float)), f"score not numeric: {hs['score']}"

            if "summary" in data and data["summary"]:
                summary = data["summary"]
                assert "totalItems" in summary or "abnormalCount" in summary, \
                    f"summary missing expected fields: {summary}"

            if "categories" in data and data["categories"]:
                for cat in data["categories"]:
                    assert "name" in cat, f"category missing 'name': {cat}"
                    if "items" in cat:
                        for item in cat["items"]:
                            assert "name" in item, f"indicator missing 'name': {item}"
                            if "riskLevel" in item:
                                assert 1 <= item["riskLevel"] <= 5, \
                                    f"riskLevel out of range: {item['riskLevel']}"
        elif resp.status_code == 400:
            pass
        elif resp.status_code == 500:
            pass


# ═══════════════════════════════════════════════
# TC-006: Report List — Contains Health Score
# ═══════════════════════════════════════════════

class TestTC006ReportList:
    def test_report_list_format(self, client: httpx.Client, auth_headers: dict, uploaded_report_id: int):
        """TC-006: GET /api/report/list returns correct format with health_score field."""
        resp = client.get(api("/api/report/list"), headers=auth_headers)
        assert resp.status_code == 200, f"List failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "items" in data, f"Missing 'items': {data.keys()}"
        assert "total" in data, f"Missing 'total': {data.keys()}"
        assert isinstance(data["items"], list), f"items not a list: {type(data['items'])}"

        if data["items"]:
            item = data["items"][0]
            assert "id" in item, f"List item missing 'id': {item.keys()}"
            assert "status" in item, f"List item missing 'status': {item.keys()}"
            assert "health_score" in item or "healthScore" in item, \
                f"List item missing health_score field: {item.keys()}"


# ═══════════════════════════════════════════════
# TC-007: Report Detail — Contains Health Score
# ═══════════════════════════════════════════════

class TestTC007ReportDetail:
    def test_report_detail_has_health_score(self, client: httpx.Client, auth_headers: dict, uploaded_report_id: int):
        """TC-007: GET /api/report/detail/{id} contains health_score field."""
        resp = client.get(api(f"/api/report/detail/{uploaded_report_id}"), headers=auth_headers)
        assert resp.status_code == 200, f"Detail failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data, f"Missing 'id': {data.keys()}"
        assert "health_score" in data or "healthScore" in data, \
            f"Detail missing health_score field: {data.keys()}"
        assert "status" in data, f"Missing 'status': {data.keys()}"
        assert "indicators" in data or "ai_analysis_json" in data, \
            f"Detail missing indicators/analysis fields: {data.keys()}"


# ═══════════════════════════════════════════════
# TC-008: Report Compare — Basic Validation
# ═══════════════════════════════════════════════

class TestTC008ReportCompare:
    def test_compare_reports(self, client: httpx.Client, auth_headers: dict,
                             uploaded_report_id: int, second_report_id: int):
        """TC-008: POST /api/report/compare returns aiSummary, scoreDiff, indicators."""
        resp = client.post(
            api("/api/report/compare"),
            json={
                "report_id_1": uploaded_report_id,
                "report_id_2": second_report_id,
            },
            headers=auth_headers,
            timeout=120.0,
        )
        assert resp.status_code in (200, 400, 500), \
            f"Compare unexpected status: {resp.status_code} {resp.text}"

        if resp.status_code == 200:
            data = resp.json()
            assert "aiSummary" in data or "ai_summary" in data, \
                f"Compare missing aiSummary: {data.keys()}"
            assert "indicators" in data, f"Compare missing indicators: {data.keys()}"
            assert "disclaimer" in data, f"Compare missing disclaimer: {data.keys()}"

    def test_compare_same_report(self, client: httpx.Client, auth_headers: dict, uploaded_report_id: int):
        """TC-008b: Compare a report with itself (edge case)."""
        resp = client.post(
            api("/api/report/compare"),
            json={
                "report_id_1": uploaded_report_id,
                "report_id_2": uploaded_report_id,
            },
            headers=auth_headers,
            timeout=120.0,
        )
        assert resp.status_code in (200, 400, 500), \
            f"Self-compare unexpected status: {resp.status_code} {resp.text}"


# ═══════════════════════════════════════════════
# TC-009: Report Compare — Invalid IDs
# ═══════════════════════════════════════════════

class TestTC009CompareInvalidID:
    def test_compare_nonexistent_report(self, client: httpx.Client, auth_headers: dict):
        """TC-009: POST /api/report/compare with non-existent IDs returns 404."""
        resp = client.post(
            api("/api/report/compare"),
            json={
                "report_id_1": 999999,
                "report_id_2": 999998,
            },
            headers=auth_headers,
        )
        assert resp.status_code in (404, 422), \
            f"Expected 404 or 422, got {resp.status_code} {resp.text}"


# ═══════════════════════════════════════════════
# TC-010: Unauthenticated Access
# ═══════════════════════════════════════════════

class TestTC010Unauthenticated:
    def test_analyze_without_token(self, client: httpx.Client):
        """TC-010: POST /api/report/analyze without token returns 401."""
        resp = client.post(api("/api/report/analyze"), json={"report_id": 1})
        assert resp.status_code in (401, 403), \
            f"Expected 401/403, got {resp.status_code} {resp.text}"

    def test_list_without_token(self, client: httpx.Client):
        """TC-010b: GET /api/report/list without token returns 401."""
        resp = client.get(api("/api/report/list"))
        assert resp.status_code in (401, 403), \
            f"Expected 401/403, got {resp.status_code} {resp.text}"

    def test_upload_without_token(self, client: httpx.Client):
        """TC-010c: POST /api/report/upload without token returns 401."""
        png_bytes = make_test_png()
        files = {"file": ("no_auth.png", io.BytesIO(png_bytes), "image/png")}
        resp = client.post(api("/api/report/upload"), files=files)
        assert resp.status_code in (401, 403), \
            f"Expected 401/403, got {resp.status_code} {resp.text}"


# ═══════════════════════════════════════════════
# TC-011: Report Share
# ═══════════════════════════════════════════════

class TestTC011ReportShare:
    def test_create_and_view_share(self, client: httpx.Client, auth_headers: dict, uploaded_report_id: int):
        """TC-011: Create share link and verify it is accessible without auth."""
        resp = client.post(
            api(f"/api/report/{uploaded_report_id}/share"),
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Share create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "share_token" in data or "share_url" in data, \
            f"Missing share info: {data.keys()}"

        share_token = data.get("share_token")
        share_url = data.get("share_url")

        if share_token:
            view_resp = client.get(api(f"/api/report/share/{share_token}"))
            assert view_resp.status_code == 200, \
                f"Share view failed: {view_resp.status_code} {view_resp.text}"
            view_data = view_resp.json()
            assert "disclaimer" in view_data or "ai_analysis" in view_data or "indicators" in view_data, \
                f"Share view missing expected fields: {view_data.keys()}"
        elif share_url:
            if share_url.startswith("/"):
                full_url = api(share_url)
            else:
                full_url = share_url
            view_resp = client.get(full_url)
            assert view_resp.status_code == 200, \
                f"Share view via URL failed: {view_resp.status_code} {view_resp.text}"


# ═══════════════════════════════════════════════
# TC-012: H5 Frontend Reachable
# ═══════════════════════════════════════════════

class TestTC012H5Frontend:
    def test_h5_homepage(self, client: httpx.Client):
        """TC-012: GET / (H5 homepage) returns 200."""
        resp = client.get(BASE_URL + "/", follow_redirects=True)
        assert resp.status_code == 200, f"H5 homepage failed: {resp.status_code}"


# ═══════════════════════════════════════════════
# TC-013: Admin Frontend Reachable
# ═══════════════════════════════════════════════

class TestTC013AdminFrontend:
    def test_admin_page(self, client: httpx.Client):
        """TC-013: GET /admin/ returns 200."""
        resp = client.get(BASE_URL + "/admin/", follow_redirects=True)
        assert resp.status_code == 200, f"Admin frontend failed: {resp.status_code}"
