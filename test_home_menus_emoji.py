#!/usr/bin/env python3
"""
pytest-based automated API tests for home-menus Emoji feature.
Validates that backend CRUD APIs remain functional after the
front-end Emoji picker optimization.
"""
import warnings
import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
TIMEOUT = 30


@pytest.fixture(scope="module")
def admin_token():
    """TC-002 helper: obtain admin JWT token."""
    resp = requests.post(
        f"{API_URL}/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        verify=False,
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text[:300]}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def created_menu_id(auth_headers):
    """Create a test menu (emoji icon) used by later tests; cleaned up after module."""
    payload = {
        "name": "pytest_emoji_test",
        "icon_type": "emoji",
        "icon_content": "\U0001f3e5",  # 🏥
        "link_type": "internal",
        "link_url": "/pytest/emoji-test",
        "sort_order": 990,
        "is_visible": True,
    }
    resp = requests.post(
        f"{API_URL}/admin/home-menus",
        json=payload,
        headers=auth_headers,
        verify=False,
        timeout=TIMEOUT,
    )
    assert resp.status_code in (200, 201), f"Create menu failed: {resp.status_code} {resp.text[:300]}"
    menu = resp.json()
    menu_id = menu.get("id")
    assert menu_id, "Created menu has no id"

    yield menu_id

    requests.delete(
        f"{API_URL}/admin/home-menus/{menu_id}",
        headers=auth_headers,
        verify=False,
        timeout=TIMEOUT,
    )


# ---------- TC-001: Health check ----------

class TestTC001HealthCheck:
    def test_health_returns_200(self):
        resp = requests.get(f"{API_URL}/health", verify=False, timeout=TIMEOUT)
        assert resp.status_code == 200


# ---------- TC-002: Admin login ----------

class TestTC002AdminLogin:
    def test_admin_login_returns_token(self):
        resp = requests.post(
            f"{API_URL}/admin/login",
            json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("token") or data.get("access_token"), "Response missing token"


# ---------- TC-003: Get menu list ----------

class TestTC003GetMenuList:
    def test_list_menus_returns_200(self, auth_headers):
        resp = requests.get(
            f"{API_URL}/admin/home-menus",
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list), f"Unexpected shape: {list(data.keys()) if isinstance(data, dict) else type(data)}"


# ---------- TC-004: Create menu with Emoji icon ----------

class TestTC004CreateEmojiMenu:
    def test_create_menu_emoji(self, auth_headers):
        payload = {
            "name": "pytest_tc004_emoji",
            "icon_type": "emoji",
            "icon_content": "\U0001f3e5",  # 🏥
            "link_type": "internal",
            "link_url": "/pytest/tc004",
            "sort_order": 991,
            "is_visible": True,
        }
        resp = requests.post(
            f"{API_URL}/admin/home-menus",
            json=payload,
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code in (200, 201), f"Status {resp.status_code}: {resp.text[:300]}"
        menu = resp.json()
        assert menu.get("id"), "No id returned"
        assert menu["icon_type"] == "emoji"
        assert menu["icon_content"] == "\U0001f3e5"

        requests.delete(
            f"{API_URL}/admin/home-menus/{menu['id']}",
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )


# ---------- TC-005: Create menu with compound/special Emoji ----------

class TestTC005CreateSpecialEmoji:
    def test_create_compound_emoji(self, auth_headers):
        compound_emoji = "\U0001f468\u200d\u2695\ufe0f"  # 👨‍⚕️
        payload = {
            "name": "pytest_tc005_cmpd",
            "icon_type": "emoji",
            "icon_content": compound_emoji,
            "link_type": "internal",
            "link_url": "/pytest/tc005",
            "sort_order": 992,
            "is_visible": True,
        }
        resp = requests.post(
            f"{API_URL}/admin/home-menus",
            json=payload,
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code in (200, 201), f"Status {resp.status_code}: {resp.text[:300]}"
        menu = resp.json()
        assert menu["icon_content"] == compound_emoji, (
            f"UTF-8 4-byte compound emoji not stored correctly: "
            f"expected {compound_emoji!r}, got {menu['icon_content']!r}"
        )

        requests.delete(
            f"{API_URL}/admin/home-menus/{menu['id']}",
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )


# ---------- TC-006: Update menu – swap Emoji ----------

class TestTC006UpdateEmoji:
    def test_update_emoji(self, auth_headers, created_menu_id):
        new_emoji = "\U0001f9b7"  # 🦷
        resp = requests.put(
            f"{API_URL}/admin/home-menus/{created_menu_id}",
            json={"icon_content": new_emoji, "icon_type": "emoji"},
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["icon_content"] == new_emoji, (
            f"Expected {new_emoji!r}, got {data['icon_content']!r}"
        )


# ---------- TC-007: Verify updated Emoji in list ----------

class TestTC007VerifyUpdatedEmoji:
    def test_updated_emoji_persisted(self, auth_headers, created_menu_id):
        resp = requests.get(
            f"{API_URL}/admin/home-menus",
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items") if isinstance(data, dict) else data
        matched = [m for m in items if m.get("id") == created_menu_id]
        assert matched, f"Menu id={created_menu_id} not found in list"
        assert matched[0]["icon_content"] == "\U0001f9b7", (
            f"Emoji not persisted: got {matched[0]['icon_content']!r}"
        )


# ---------- TC-008: Delete test menu ----------

class TestTC008DeleteMenu:
    def test_delete_menu(self, auth_headers):
        payload = {
            "name": "pytest_tc008_delete",
            "icon_type": "emoji",
            "icon_content": "\U0001f5d1",  # 🗑
            "link_type": "internal",
            "link_url": "/pytest/tc008",
            "sort_order": 993,
            "is_visible": True,
        }
        resp = requests.post(
            f"{API_URL}/admin/home-menus",
            json=payload,
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code in (200, 201)
        menu_id = resp.json()["id"]

        del_resp = requests.delete(
            f"{API_URL}/admin/home-menus/{menu_id}",
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        assert del_resp.status_code in (200, 204), (
            f"Delete failed: {del_resp.status_code} {del_resp.text[:200]}"
        )

        verify_resp = requests.get(
            f"{API_URL}/admin/home-menus",
            headers=auth_headers,
            verify=False,
            timeout=TIMEOUT,
        )
        items = verify_resp.json().get("items") if isinstance(verify_resp.json(), dict) else verify_resp.json()
        assert not any(m.get("id") == menu_id for m in items), "Deleted menu still present"


# ---------- TC-009: Unauthorized access ----------

class TestTC009Unauthorized:
    def test_no_token_returns_401(self):
        resp = requests.get(
            f"{API_URL}/admin/home-menus",
            verify=False,
            timeout=TIMEOUT,
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without token, got {resp.status_code}"
        )


# ---------- TC-010: Admin frontend reachable ----------

class TestTC010AdminFrontend:
    def test_admin_page_accessible(self):
        resp = requests.get(
            f"{BASE_URL}/admin/",
            verify=False,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        assert resp.status_code == 200, f"Admin page status {resp.status_code}"
        assert len(resp.content) > 500, "Admin page content too small – likely not a real page"

    def test_home_menus_page_accessible(self):
        resp = requests.get(
            f"{BASE_URL}/admin/home-menus",
            verify=False,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        assert resp.status_code == 200, f"Home-menus page status {resp.status_code}"
