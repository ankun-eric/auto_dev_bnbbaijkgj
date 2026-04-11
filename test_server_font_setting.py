"""
Non-UI automated tests for font size setting feature.
Target: https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""
import httpx
import pytest

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
TIMEOUT = 15


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_URL, timeout=TIMEOUT, verify=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    """Get token via admin login, then fallback to regular login."""
    resp = client.post("/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token

    resp2 = client.post("/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    if resp2.status_code == 200:
        data = resp2.json()
        token = data.get("access_token") or data.get("token")
        if token:
            return token

    pytest.skip(f"Cannot authenticate: admin_login={resp.status_code}, auth_login={resp2.status_code}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthCheck:
    def test_01_health_endpoint_reachable(self, client):
        """TC-01: Health check endpoint returns 200 with ok status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestH5Accessible:
    def test_13_h5_home_page(self):
        """TC-13: H5 frontend home page is accessible."""
        with httpx.Client(timeout=TIMEOUT, verify=True) as c:
            resp = c.get(f"{BASE_URL}/", follow_redirects=True)
            assert resp.status_code == 200


class TestAdminLogin:
    def test_02_admin_login_returns_token(self, client):
        """TC-02: Admin login with correct credentials returns token."""
        resp = client.post("/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data or "access_token" in data

    def test_03_sms_code_endpoint_exists(self, client):
        """TC-03: SMS code endpoint exists and is reachable."""
        resp = client.post("/auth/sms-code", json={"phone": "13800138999", "type": "login"})
        assert resp.status_code in (200, 201, 429, 403, 400)


class TestFontSettingAuth:
    def test_11_get_font_setting_without_auth(self, client):
        """TC-11: GET /user/font-setting without token returns 401."""
        resp = client.get("/user/font-setting")
        assert resp.status_code == 401

    def test_12_put_font_setting_without_auth(self, client):
        """TC-12: PUT /user/font-setting without token returns 401."""
        resp = client.put("/user/font-setting", json={"font_size_level": "large"})
        assert resp.status_code == 401


class TestFontSettingCRUD:
    def test_04_get_default_font_setting(self, client, auth_headers):
        """TC-04: GET font setting returns a valid font_size_level."""
        resp = client.get("/user/font-setting", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "font_size_level" in data
        assert data["font_size_level"] in ("standard", "large", "extra_large")

    def test_05_update_font_to_large(self, client, auth_headers):
        """TC-05: PUT font setting to 'large' succeeds."""
        resp = client.put(
            "/user/font-setting",
            json={"font_size_level": "large"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["font_size_level"] == "large"

    def test_06_confirm_font_is_large(self, client, auth_headers):
        """TC-06: GET confirms font setting is now 'large'."""
        resp = client.get("/user/font-setting", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["font_size_level"] == "large"

    def test_07_update_font_to_extra_large(self, client, auth_headers):
        """TC-07: PUT font setting to 'extra_large' succeeds."""
        resp = client.put(
            "/user/font-setting",
            json={"font_size_level": "extra_large"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["font_size_level"] == "extra_large"

    def test_08_confirm_font_is_extra_large(self, client, auth_headers):
        """TC-08: GET confirms font setting is now 'extra_large'."""
        resp = client.get("/user/font-setting", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["font_size_level"] == "extra_large"

    def test_09_restore_font_to_standard(self, client, auth_headers):
        """TC-09: PUT font setting back to 'standard' succeeds."""
        resp = client.put(
            "/user/font-setting",
            json={"font_size_level": "standard"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["font_size_level"] == "standard"

    def test_10_invalid_font_value_returns_422(self, client, auth_headers):
        """TC-10: PUT invalid font size value returns 422."""
        resp = client.put(
            "/user/font-setting",
            json={"font_size_level": "invalid_size"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
