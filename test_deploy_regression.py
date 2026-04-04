"""
Regression tests for bini-health deployment.
Validates all services are accessible and API endpoints behave correctly.
"""

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
H5_BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
ADMIN_BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin"
TIMEOUT = 30


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.verify = False
    return s


# ── a. API Health Check ──────────────────────────────────────────────

class TestAPIHealthCheck:
    def test_api_health_returns_200(self, http):
        """GET /api/health should return 200"""
        resp = http.get(f"{API_BASE}/health", timeout=TIMEOUT)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── b. H5 Frontend Reachability ──────────────────────────────────────

class TestH5Frontend:
    def test_h5_returns_200_with_html(self, http):
        """GET H5_BASE/ should return 200 and contain HTML"""
        resp = http.get(f"{H5_BASE}/", timeout=TIMEOUT)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}"
        )
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct, f"Expected text/html, got content-type: {ct}"


# ── c. Admin Panel Reachability ──────────────────────────────────────

class TestAdminPanel:
    def test_admin_returns_200_with_html(self, http):
        """GET ADMIN_BASE/ should return 200 and contain HTML"""
        resp = http.get(f"{ADMIN_BASE}/", timeout=TIMEOUT)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}"
        )
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct, f"Expected text/html, got content-type: {ct}"


# ── d. Register Settings API ────────────────────────────────────────

class TestRegisterSettings:
    def test_register_settings_returns_200(self, http):
        """GET /api/auth/register-settings should return 200"""
        resp = http.get(f"{API_BASE}/auth/register-settings", timeout=TIMEOUT)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. Body: {resp.text[:300]}"
        )
        data = resp.json()
        assert isinstance(data, dict), "Response should be a JSON object"


# ── e. SMS Code – Missing Params ────────────────────────────────────

class TestSmsCode:
    def test_sms_code_missing_params_returns_422_or_400(self, http):
        """POST /api/auth/sms-code with empty body should return 422 or 400"""
        resp = http.post(f"{API_BASE}/auth/sms-code", json={}, timeout=TIMEOUT)
        assert resp.status_code in (422, 400), (
            f"Expected 422 or 400, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── f. Admin Login – Missing Params ─────────────────────────────────

class TestAdminLogin:
    def test_admin_login_missing_params_returns_error(self, http):
        """POST /api/auth/admin-login with empty body should return error status"""
        resp = http.post(f"{API_BASE}/auth/admin-login", json={}, timeout=TIMEOUT)
        assert resp.status_code in (422, 400, 404), (
            f"Expected 422, 400, or 404, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── g. AI Config – Requires Auth ────────────────────────────────────

class TestAIConfig:
    def test_ai_config_unauthorized_returns_401_or_403(self, http):
        """GET /api/admin/ai-config without token should return 401 or 403"""
        resp = http.get(f"{API_BASE}/admin/ai-config", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── h. Admin Dashboard – Requires Auth ──────────────────────────────

class TestAdminDashboard:
    def test_dashboard_unauthorized_returns_401_or_403(self, http):
        """GET /api/admin/dashboard without token should return 401 or 403"""
        resp = http.get(f"{API_BASE}/admin/dashboard", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── i. SMS Admin Config – Requires Auth ─────────────────────────────

class TestSmsAdminConfig:
    def test_sms_config_unauthorized_returns_401_or_403(self, http):
        """GET /api/admin/sms/config without token should return 401 or 403"""
        resp = http.get(f"{API_BASE}/admin/sms/config", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── j. Merchant Stores – Requires Auth ──────────────────────────────

class TestMerchantStores:
    def test_merchant_stores_unauthorized_returns_401_or_403(self, http):
        """GET /api/merchant/stores without token should return 401 or 403"""
        resp = http.get(f"{API_BASE}/merchant/stores", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403, got {resp.status_code}. Body: {resp.text[:300]}"
        )


# ── k. Uploads Path ─────────────────────────────────────────────────

class TestUploadsPath:
    def test_uploads_route_reachable(self, http):
        """GET /uploads/ should not return 502/503/504 (route is configured)"""
        resp = http.get(
            f"https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/",
            timeout=TIMEOUT,
        )
        assert resp.status_code not in (502, 503, 504), (
            f"Uploads route returned gateway error {resp.status_code}"
        )
        assert resp.status_code in (200, 403, 404, 301, 302), (
            f"Unexpected status {resp.status_code} for /uploads/"
        )


# ── l. H5 Static Assets (_next) ─────────────────────────────────────

class TestH5StaticAssets:
    def test_h5_next_route_works(self, http):
        """H5 _next route should be functional (not 502/503)"""
        page_resp = http.get(f"{H5_BASE}/", timeout=TIMEOUT)
        if page_resp.status_code != 200:
            pytest.skip("H5 homepage not reachable, cannot test static assets")

        import re
        assets = re.findall(r'(?:src|href)="(/_next/[^"]+)"', page_resp.text)
        if not assets:
            assets = re.findall(r'(?:src|href)="([^"]*_next/[^"]+)"', page_resp.text)

        if not assets:
            resp = http.get(f"{H5_BASE}/_next/data/", timeout=TIMEOUT)
            assert resp.status_code not in (502, 503, 504), (
                f"_next route returned gateway error {resp.status_code}"
            )
            return

        asset_url = assets[0]
        if asset_url.startswith("/"):
            asset_url = f"https://newbb.test.bangbangvip.com{asset_url}"
        elif not asset_url.startswith("http"):
            asset_url = f"{H5_BASE}/{asset_url}"

        resp = http.get(asset_url, timeout=TIMEOUT)
        assert resp.status_code == 200, (
            f"H5 static asset returned {resp.status_code}: {asset_url}"
        )


# ── m. Admin Static Assets (_next) ──────────────────────────────────

class TestAdminStaticAssets:
    def test_admin_next_route_works(self, http):
        """Admin _next route should be functional (not 502/503)"""
        page_resp = http.get(f"{ADMIN_BASE}/", timeout=TIMEOUT)
        if page_resp.status_code != 200:
            pytest.skip("Admin homepage not reachable, cannot test static assets")

        import re
        assets = re.findall(r'(?:src|href)="(/_next/[^"]+)"', page_resp.text)
        if not assets:
            assets = re.findall(r'(?:src|href)="([^"]*_next/[^"]+)"', page_resp.text)

        if not assets:
            resp = http.get(f"{ADMIN_BASE}/_next/data/", timeout=TIMEOUT)
            assert resp.status_code not in (502, 503, 504), (
                f"_next route returned gateway error {resp.status_code}"
            )
            return

        asset_url = assets[0]
        if asset_url.startswith("/"):
            asset_url = f"https://newbb.test.bangbangvip.com{asset_url}"
        elif not asset_url.startswith("http"):
            asset_url = f"{ADMIN_BASE}/{asset_url}"

        resp = http.get(asset_url, timeout=TIMEOUT)
        assert resp.status_code == 200, (
            f"Admin static asset returned {resp.status_code}: {asset_url}"
        )
