"""
Server-side automated tests for the checkup report smart interpretation feature.
"""

import io
import struct
import zlib

import httpx
import pytest

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
TIMEOUT = 30.0


def api(path: str) -> str:
    return f"{BASE_URL}{path}"


def make_test_png(width=400, height=300) -> bytes:
    """Generate a valid PNG that passes quality checks (>=200x200, >=10KB)."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    import random
    random.seed(42)
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"
        for x in range(width):
            r = (x * 7 + y * 13 + (x ^ y)) & 0xFF
            g = (x * 11 + y * 3 + (x * y)) & 0xFF
            b = (x * 5 + y * 17 + (x + y)) & 0xFF
            raw_data += bytes([r, g, b])
    idat_data = zlib.compress(raw_data, 1)
    return header + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", idat_data) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(verify=False, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token(client: httpx.Client):
    resp = client.post(api("/api/auth/login"), json={"phone": "13800000000", "password": "admin123"})
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("access_token")
    assert token, f"No access_token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def uploaded_report_id(client: httpx.Client, admin_headers: dict):
    png_bytes = make_test_png()
    files = {"file": ("test_report.png", io.BytesIO(png_bytes), "image/png")}
    resp = client.post(api("/api/report/upload"), files=files, headers=admin_headers)
    if resp.status_code == 503:
        pytest.skip("OCR service disabled, cannot upload report")
    assert resp.status_code == 200, f"Upload failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "id" in data
    return data["id"]


# ─────────────────────────────────────────────
# 1. Admin login
# ─────────────────────────────────────────────

class TestAdminLogin:
    def test_admin_login_success(self, client: httpx.Client):
        resp = client.post(api("/api/auth/login"), json={"phone": "13800000000", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data.get("user", {}).get("phone") == "13800000000"

    def test_admin_login_wrong_password(self, client: httpx.Client):
        resp = client.post(api("/api/auth/login"), json={"phone": "13800000000", "password": "wrong"})
        assert resp.status_code == 400


# ─────────────────────────────────────────────
# 2. OCR Config (admin)
# ─────────────────────────────────────────────

class TestOcrConfig:
    def test_get_ocr_config(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(api("/api/admin/ocr/config"), headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "ocr_type" in data

    def test_update_ocr_config(self, client: httpx.Client, admin_headers: dict):
        resp = client.put(
            api("/api/admin/ocr/config"),
            json={"enabled": True, "api_key": "test_key", "ocr_type": "general_basic"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["ocr_type"] == "general_basic"

    def test_get_ocr_config_no_auth(self, client: httpx.Client):
        resp = client.get(api("/api/admin/ocr/config"))
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# 3. Report upload
# ─────────────────────────────────────────────

class TestReportUpload:
    def test_upload_png(self, client: httpx.Client, admin_headers: dict):
        png_bytes = make_test_png()
        files = {"file": ("checkup.png", io.BytesIO(png_bytes), "image/png")}
        resp = client.post(api("/api/report/upload"), files=files, headers=admin_headers)
        if resp.status_code == 503:
            pytest.skip("OCR service disabled")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["file_type"] == "image"
        assert data["id"] > 0

    def test_upload_invalid_type(self, client: httpx.Client, admin_headers: dict):
        files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        resp = client.post(api("/api/report/upload"), files=files, headers=admin_headers)
        assert resp.status_code == 400

    def test_upload_no_auth(self, client: httpx.Client):
        png_bytes = make_test_png()
        files = {"file": ("checkup.png", io.BytesIO(png_bytes), "image/png")}
        resp = client.post(api("/api/report/upload"), files=files)
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# 4. Report list
# ─────────────────────────────────────────────

class TestReportList:
    def test_list_reports(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(api("/api/report/list"), headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["page"] == 1

    def test_list_reports_pagination(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(api("/api/report/list?page=1&page_size=5"), headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 5

    def test_list_reports_no_auth(self, client: httpx.Client):
        resp = client.get(api("/api/report/list"))
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# 5. Report detail
# ─────────────────────────────────────────────

class TestReportDetail:
    def test_get_detail(self, client: httpx.Client, admin_headers: dict, uploaded_report_id: int):
        resp = client.get(api(f"/api/report/detail/{uploaded_report_id}"), headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == uploaded_report_id
        assert "status" in data
        assert "indicators" in data

    def test_get_detail_not_found(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(api("/api/report/detail/999999"), headers=admin_headers)
        assert resp.status_code == 404

    def test_get_detail_no_auth(self, client: httpx.Client):
        resp = client.get(api("/api/report/detail/1"))
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# 6. Trend data
# ─────────────────────────────────────────────

class TestTrend:
    def test_get_trend_empty(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(api("/api/report/trend/血红蛋白"), headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator_name"] == "血红蛋白"
        assert isinstance(data["data_points"], list)

    def test_get_trend_no_auth(self, client: httpx.Client):
        resp = client.get(api("/api/report/trend/血红蛋白"))
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# 7. Alerts
# ─────────────────────────────────────────────

class TestAlerts:
    def test_get_alerts(self, client: httpx.Client, admin_headers: dict):
        resp = client.get(api("/api/report/alerts"), headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_alerts_no_auth(self, client: httpx.Client):
        resp = client.get(api("/api/report/alerts"))
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# 8. Share
# ─────────────────────────────────────────────

class TestShare:
    def test_create_share(self, client: httpx.Client, admin_headers: dict, uploaded_report_id: int):
        resp = client.post(
            api("/api/report/share"),
            json={"report_id": uploaded_report_id},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "share_token" in data
        assert "share_url" in data
        assert "expires_at" in data

    def test_view_share(self, client: httpx.Client, admin_headers: dict, uploaded_report_id: int):
        create_resp = client.post(
            api("/api/report/share"),
            json={"report_id": uploaded_report_id},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200
        token = create_resp.json()["share_token"]

        view_resp = client.get(api(f"/api/report/share/{token}"))
        assert view_resp.status_code == 200
        data = view_resp.json()
        assert "indicators" in data
        assert "disclaimer" in data

    def test_view_share_invalid_token(self, client: httpx.Client):
        resp = client.get(api("/api/report/share/nonexistent_token_abc123"))
        assert resp.status_code == 404

    def test_create_share_no_auth(self, client: httpx.Client):
        resp = client.post(api("/api/report/share"), json={"report_id": 1})
        assert resp.status_code == 401

    def test_create_share_not_found(self, client: httpx.Client, admin_headers: dict):
        resp = client.post(
            api("/api/report/share"),
            json={"report_id": 999999},
            headers=admin_headers,
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────
# 9. Unauthenticated access
# ─────────────────────────────────────────────

class TestUnauthorized:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/report/list"),
            ("GET", "/api/report/detail/1"),
            ("GET", "/api/report/trend/test"),
            ("GET", "/api/report/alerts"),
            ("GET", "/api/admin/ocr/config"),
        ],
    )
    def test_endpoints_require_auth(self, client: httpx.Client, method: str, path: str):
        resp = client.request(method, api(path))
        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code}, expected 401/403"
        )


# ─────────────────────────────────────────────
# 10. Health check
# ─────────────────────────────────────────────

class TestHealthCheck:
    def test_health(self, client: httpx.Client):
        resp = client.get(api("/api/health"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
