"""
Non-UI automated tests for Member Level Management API (会员等级管理).
Target: deployed server at https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""

import pytest
import requests

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
TIMEOUT = 15


@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and return the bearer token."""
    resp = requests.post(
        f"{BASE_URL}/admin/login",
        json={"phone": "13800000000", "password": "admin123"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


CAMEL_CASE_FIELDS = {"name", "minPoints", "maxPoints", "discount", "icon", "color", "memberCount"}
SNAKE_CASE_FIELDS = {"level_name", "min_points", "max_points", "discount_rate", "member_count"}


class TestAdminLogin:
    def test_login_success(self):
        resp = requests.post(
            f"{BASE_URL}/admin/login",
            json={"phone": "13800000000", "password": "admin123"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self):
        resp = requests.post(
            f"{BASE_URL}/admin/login",
            json={"phone": "13800000000", "password": "wrong"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 400


class TestGetLevels:
    def test_get_levels_returns_200(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        assert resp.status_code == 200

    def test_get_levels_has_items(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_levels_camel_case_fields(self, auth_headers):
        """Verify returned fields are camelCase, NOT snake_case."""
        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        data = resp.json()
        items = data.get("items", [])
        if not items:
            pytest.skip("No member levels in database to verify field names")

        first = items[0]
        for field in CAMEL_CASE_FIELDS:
            assert field in first, f"Missing camelCase field '{field}' in response. Keys: {list(first.keys())}"

    def test_get_levels_no_snake_case(self, auth_headers):
        """Verify no snake_case field names leak into response."""
        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        data = resp.json()
        items = data.get("items", [])
        if not items:
            pytest.skip("No member levels in database")

        first = items[0]
        for field in SNAKE_CASE_FIELDS:
            assert field not in first, f"Snake_case field '{field}' should NOT appear. Keys: {list(first.keys())}"

    def test_benefits_is_string(self, auth_headers):
        """benefits should be returned as a string, not a dict."""
        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        items = resp.json().get("items", [])
        if not items:
            pytest.skip("No member levels in database")

        for item in items:
            benefits = item.get("benefits")
            assert not isinstance(benefits, dict), (
                f"benefits for level '{item.get('name')}' is a dict, expected string. Value: {benefits}"
            )

    def test_discount_is_integer(self, auth_headers):
        """discount should be an integer like 95 (meaning 95折), not a float like 0.95."""
        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        items = resp.json().get("items", [])
        if not items:
            pytest.skip("No member levels in database")

        for item in items:
            discount = item.get("discount")
            assert isinstance(discount, int), (
                f"discount for '{item.get('name')}' is {type(discount).__name__}={discount}, expected int"
            )
            assert discount >= 1, (
                f"discount for '{item.get('name')}' is {discount}, looks like a raw rate not a percentage"
            )


class TestCreateLevel:
    def test_create_level_with_camel_case(self, auth_headers):
        """POST with camelCase fields should succeed."""
        payload = {
            "name": "自动化测试等级",
            "icon": "test-icon",
            "minPoints": 99900,
            "maxPoints": 99999,
            "discount": 88,
            "benefits": "自动化测试专属权益",
            "color": "#ff0000",
        }
        resp = requests.post(
            f"{BASE_URL}/admin/points/levels",
            json=payload,
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200, f"Create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data, f"Response missing 'id': {data}"
        TestCreateLevel.created_id = data["id"]

    def test_created_level_appears_in_list(self, auth_headers):
        """The newly created level should appear in GET list."""
        created_id = getattr(TestCreateLevel, "created_id", None)
        if not created_id:
            pytest.skip("No level was created in previous test")

        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        items = resp.json().get("items", [])
        ids = [item["id"] for item in items]
        assert created_id in ids, f"Created level id={created_id} not found in list. IDs: {ids}"


class TestUpdateLevel:
    def test_put_update_level(self, auth_headers):
        """PUT /points/levels/{id} should return 200."""
        created_id = getattr(TestCreateLevel, "created_id", None)
        if not created_id:
            pytest.skip("No level was created")

        payload = {
            "name": "自动化测试等级_已修改",
            "icon": "updated-icon",
            "minPoints": 99900,
            "maxPoints": 99999,
            "discount": 90,
            "benefits": "已修改权益",
            "color": "#00ff00",
        }
        resp = requests.put(
            f"{BASE_URL}/admin/points/levels/{created_id}",
            json=payload,
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200, f"PUT update failed: {resp.status_code} {resp.text}"

    def test_updated_values_reflected(self, auth_headers):
        """After PUT, GET should reflect the updated values."""
        created_id = getattr(TestCreateLevel, "created_id", None)
        if not created_id:
            pytest.skip("No level was created")

        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        items = resp.json().get("items", [])
        updated = next((i for i in items if i["id"] == created_id), None)
        assert updated is not None, f"Level id={created_id} not found after update"
        assert updated["name"] == "自动化测试等级_已修改", f"Name not updated: {updated['name']}"
        assert updated["discount"] == 90, f"Discount not updated: {updated['discount']}"
        assert updated["color"] == "#00ff00", f"Color not updated: {updated['color']}"


class TestDeleteLevel:
    def test_delete_level(self, auth_headers):
        """DELETE /points/levels/{id} should return 200."""
        created_id = getattr(TestCreateLevel, "created_id", None)
        if not created_id:
            pytest.skip("No level was created")

        resp = requests.delete(
            f"{BASE_URL}/admin/points/levels/{created_id}",
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200, f"DELETE failed: {resp.status_code} {resp.text}"

    def test_deleted_level_not_in_list(self, auth_headers):
        """After DELETE, the level should no longer appear in GET."""
        created_id = getattr(TestCreateLevel, "created_id", None)
        if not created_id:
            pytest.skip("No level was created")

        resp = requests.get(f"{BASE_URL}/admin/points/levels", headers=auth_headers, timeout=TIMEOUT)
        items = resp.json().get("items", [])
        ids = [item["id"] for item in items]
        assert created_id not in ids, f"Deleted level id={created_id} still appears in list"

    def test_delete_nonexistent_returns_404(self, auth_headers):
        """DELETE a non-existent level should return 404."""
        resp = requests.delete(
            f"{BASE_URL}/admin/points/levels/999999",
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 404
