import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
VERIFY_SSL = False


@pytest.fixture(scope="session")
def admin_token():
    resp = requests.post(
        f"{BASE_URL}/admin/login",
        json={"phone": "13800000000", "password": "admin123"},
        verify=VERIFY_SSL,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token") or data.get("data", {}).get("access_token") or data.get("data", {}).get("token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- 1. Admin Login ----------

class TestAdminLogin:
    def test_login_success(self):
        resp = requests.post(
            f"{BASE_URL}/admin/login",
            json={"phone": "13800000000", "password": "admin123"},
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200
        data = resp.json()
        token = data.get("access_token") or data.get("token") or data.get("data", {}).get("access_token") or data.get("data", {}).get("token")
        assert token is not None, f"Token missing in: {data}"


# ---------- 2-5. Service Categories CRUD ----------

class TestServiceCategories:
    _created_id = None

    def test_list_categories(self, auth_headers):
        resp = requests.get(
            f"{BASE_URL}/admin/services/categories",
            headers=auth_headers,
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200, f"List failed: {resp.status_code} {resp.text}"
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data") or data.get("items") or data.get("categories") or []
        if isinstance(items, dict):
            items = items.get("items") or items.get("categories") or []
        assert len(items) > 0, f"Expected categories, got: {data}"
        names = [c.get("name", "") for c in items]
        expected = ["健康食品", "口腔服务", "体检服务", "专家咨询", "养老服务"]
        for name in expected:
            assert name in names, f"Expected category '{name}' in {names}"

    def test_create_category(self, auth_headers):
        resp = requests.post(
            f"{BASE_URL}/admin/services/categories",
            headers=auth_headers,
            json={"name": "自动化测试分类", "sort_order": 99, "is_active": True},
            verify=VERIFY_SSL,
        )
        assert resp.status_code in (200, 201), f"Create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        item = data if "id" in data else data.get("data", {})
        assert item.get("id"), f"No id in created category: {data}"
        TestServiceCategories._created_id = item["id"]

    def test_update_category(self, auth_headers):
        cid = TestServiceCategories._created_id
        assert cid, "No category id from create step"
        resp = requests.put(
            f"{BASE_URL}/admin/services/categories/{cid}",
            headers=auth_headers,
            json={"name": "自动化测试分类_已修改", "sort_order": 100},
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200, f"Update failed: {resp.status_code} {resp.text}"
        data = resp.json()
        item = data if "name" in data else data.get("data", {})
        assert item.get("name") == "自动化测试分类_已修改", f"Name not updated: {data}"

    def test_delete_category(self, auth_headers):
        cid = TestServiceCategories._created_id
        assert cid, "No category id from create step"
        resp = requests.delete(
            f"{BASE_URL}/admin/services/categories/{cid}",
            headers=auth_headers,
            verify=VERIFY_SSL,
        )
        assert resp.status_code in (200, 204), f"Delete failed: {resp.status_code} {resp.text}"


# ---------- 6-9. Service Items CRUD ----------

class TestServiceItems:
    _created_id = None
    _category_id = None

    def test_list_items(self, auth_headers):
        resp = requests.get(
            f"{BASE_URL}/admin/services/items",
            headers=auth_headers,
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200, f"List failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert isinstance(data, (list, dict)), f"Unexpected response type: {data}"
        if isinstance(data, dict):
            assert "items" in data or "data" in data, f"Missing items key: {data}"

    def test_create_item(self, auth_headers):
        cats_resp = requests.get(
            f"{BASE_URL}/admin/services/categories",
            headers=auth_headers,
            verify=VERIFY_SSL,
        )
        cats_data = cats_resp.json()
        cats = cats_data if isinstance(cats_data, list) else cats_data.get("data") or cats_data.get("items") or cats_data.get("categories") or []
        if isinstance(cats, dict):
            cats = cats.get("items") or cats.get("categories") or []
        assert len(cats) > 0, "Need at least one category to create item"
        TestServiceItems._category_id = cats[0]["id"]

        resp = requests.post(
            f"{BASE_URL}/admin/services/items",
            headers=auth_headers,
            json={
                "name": "自动化测试服务项",
                "category_id": TestServiceItems._category_id,
                "price": 99.9,
                "description": "测试用服务项",
                "is_active": True,
                "sort_order": 99,
            },
            verify=VERIFY_SSL,
        )
        assert resp.status_code in (200, 201), f"Create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        item = data if "id" in data else data.get("data", {})
        assert item.get("id"), f"No id in created item: {data}"
        TestServiceItems._created_id = item["id"]

    def test_update_item_with_category_change(self, auth_headers):
        iid = TestServiceItems._created_id
        assert iid, "No item id from create step"

        cats_resp = requests.get(
            f"{BASE_URL}/admin/services/categories",
            headers=auth_headers,
            verify=VERIFY_SSL,
        )
        cats_data = cats_resp.json()
        cats = cats_data if isinstance(cats_data, list) else cats_data.get("data") or cats_data.get("items") or cats_data.get("categories") or []
        if isinstance(cats, dict):
            cats = cats.get("items") or cats.get("categories") or []

        new_cat_id = TestServiceItems._category_id
        if len(cats) > 1:
            for c in cats:
                if c["id"] != TestServiceItems._category_id:
                    new_cat_id = c["id"]
                    break

        resp = requests.put(
            f"{BASE_URL}/admin/services/items/{iid}",
            headers=auth_headers,
            json={
                "name": "自动化测试服务项_已修改",
                "category_id": new_cat_id,
                "price": 199.9,
            },
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200, f"Update failed: {resp.status_code} {resp.text}"
        data = resp.json()
        item = data if "name" in data else data.get("data", {})
        assert item.get("name") == "自动化测试服务项_已修改", f"Name not updated: {data}"

    def test_delete_item(self, auth_headers):
        iid = TestServiceItems._created_id
        assert iid, "No item id from create step"
        resp = requests.delete(
            f"{BASE_URL}/admin/services/items/{iid}",
            headers=auth_headers,
            verify=VERIFY_SSL,
        )
        assert resp.status_code in (200, 204), f"Delete failed: {resp.status_code} {resp.text}"


# ---------- 10-11. User-facing public endpoints ----------

class TestPublicEndpoints:
    def test_public_categories(self):
        resp = requests.get(
            f"{BASE_URL}/services/categories",
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200, f"Public categories failed: {resp.status_code} {resp.text}"
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data") or data.get("items") or data.get("categories") or []
        if isinstance(items, dict):
            items = items.get("items") or items.get("categories") or []
        assert len(items) > 0, f"Expected active categories, got: {data}"
        for c in items:
            if "is_active" in c:
                assert c["is_active"] is True, f"Inactive category returned: {c}"

    def test_public_items(self):
        resp = requests.get(
            f"{BASE_URL}/services/items",
            verify=VERIFY_SSL,
        )
        assert resp.status_code == 200, f"Public items failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert isinstance(data, (list, dict)), f"Unexpected response type: {data}"
        items = data if isinstance(data, list) else data.get("data") or data.get("items") or []
        if isinstance(items, dict):
            items = items.get("items") or []
        for i in items:
            if "is_active" in i:
                assert i["is_active"] is True, f"Inactive item returned: {i}"
