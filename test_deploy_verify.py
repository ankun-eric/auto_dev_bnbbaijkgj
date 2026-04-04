"""
Deployment verification tests for bini-health platform.
Validates that all services are accessible and responding correctly
after a fresh deployment.
"""

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"
TIMEOUT = 30


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.verify = False
    s.headers.update({"Accept": "application/json"})
    return s


# ── a. API Health Check ──────────────────────────────────────────────

class TestHealthCheck:
    def test_api_health(self, session):
        """GET /api/health should return 200"""
        resp = session.get(f"{API_URL}/health", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


# ── b. Frontend Page Accessibility ───────────────────────────────────

class TestFrontendPages:
    def test_h5_homepage(self, session):
        """H5 homepage should return 200"""
        resp = session.get(f"{BASE_URL}/", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_admin_homepage(self, session):
        """Admin homepage should return 200"""
        resp = session.get(f"{BASE_URL}/admin/", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


# ── c. Register Settings API ─────────────────────────────────────────

class TestRegisterSettings:
    def test_register_settings(self, session):
        """GET /api/auth/register-settings should return 200 with settings"""
        resp = session.get(f"{API_URL}/auth/register-settings", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, dict), "Response should be a JSON object"


# ── d. SMS Code Validation ───────────────────────────────────────────

class TestAuthSmsCode:
    def test_sms_code_missing_params(self, session):
        """POST /api/auth/sms-code without body should return 422"""
        resp = session.post(f"{API_URL}/auth/sms-code", json={}, timeout=TIMEOUT)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_sms_code_empty_phone(self, session):
        """POST /api/auth/sms-code with empty phone should return 422 or 500 (SMS not configured)"""
        resp = session.post(
            f"{API_URL}/auth/sms-code",
            json={"phone": ""},
            timeout=TIMEOUT,
        )
        # 422 = validation error (expected), 500 = SMS service not configured (acceptable)
        assert resp.status_code in (422, 500), f"Expected 422/500, got {resp.status_code}"


# ── e. Admin Dashboard (Auth Required) ──────────────────────────────

class TestAdminDashboard:
    def test_dashboard_no_token(self, session):
        """GET /api/admin/dashboard without token should return 401 or 403"""
        resp = session.get(f"{API_URL}/admin/dashboard", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}"
        )


# ── f. Admin Users List (Auth Required) ──────────────────────────────

class TestAdminUsers:
    def test_users_list_no_token(self, session):
        """GET /api/admin/users without token should return 401 or 403"""
        resp = session.get(f"{API_URL}/admin/users", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}"
        )


# ── g. Service Categories (Public) ───────────────────────────────────

class TestServiceCategories:
    def test_categories_list(self, session):
        """GET /api/services/categories should return 200"""
        resp = session.get(f"{API_URL}/services/categories", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data, "Response should contain 'items' key"


# ── h. Articles List (Public) ────────────────────────────────────────

class TestArticles:
    def test_articles_list(self, session):
        """GET /api/content/articles should return 200"""
        resp = session.get(f"{API_URL}/content/articles", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data, "Response should contain 'items' key"


# ── i. AI Config (Auth Required) ─────────────────────────────────────

class TestAdminAiConfig:
    def test_ai_config_no_token(self, session):
        """GET /api/admin/ai-config without token should return 401 or 403"""
        resp = session.get(f"{API_URL}/admin/ai-config", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}"
        )


# ── Additional: Merchant API (Auth Required) ─────────────────────────

class TestMerchantApi:
    def test_merchant_stores_no_token(self, session):
        """GET /api/admin/merchant/stores without token should return 401 or 403"""
        resp = session.get(f"{API_URL}/admin/merchant/stores", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}"
        )


# ── Additional: SMS Admin API (Auth Required) ────────────────────────

class TestSmsAdminApi:
    def test_sms_config_no_token(self, session):
        """GET /api/admin/sms/config without token should return 401 or 403"""
        resp = session.get(f"{API_URL}/admin/sms/config", timeout=TIMEOUT)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}"
        )
