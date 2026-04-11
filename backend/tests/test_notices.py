"""
Server-side API tests for HomeNotice (公告栏) feature.
Run against the deployed server via HTTPS.
"""
import pytest
import requests
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings()

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
SESSION = requests.Session()
SESSION.verify = False


def get_admin_token():
    resp = SESSION.post(
        f"{BASE_URL}/api/auth/login",
        json={"phone": "13800000000", "password": "admin123"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("access_token")
    assert token, "No access_token in login response"
    return token


@pytest.fixture(scope="module")
def admin_headers():
    token = get_admin_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def created_notice_id(admin_headers):
    """Create a notice and return its ID; delete after module tests."""
    now = datetime.utcnow()
    data = {
        "content": "自动化测试公告内容",
        "link_url": "/health-profile",
        "start_time": (now - timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
        "is_enabled": True,
        "sort_order": 0,
    }
    resp = SESSION.post(f"{BASE_URL}/api/admin/notices", json=data, headers=admin_headers)
    assert resp.status_code in (200, 201), f"Create notice failed: {resp.status_code} {resp.text}"
    notice_id = resp.json().get("id")
    assert notice_id, "No id in create response"
    yield notice_id
    # Cleanup
    SESSION.delete(f"{BASE_URL}/api/admin/notices/{notice_id}", headers=admin_headers)


class TestPublicNoticesAPI:
    def test_get_active_notices_returns_200(self):
        resp = SESSION.get(f"{BASE_URL}/api/notices/active")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_active_notices_returns_items_list(self):
        resp = SESSION.get(f"{BASE_URL}/api/notices/active")
        data = resp.json()
        assert "items" in data, f"Response missing 'items' key: {data}"
        assert isinstance(data["items"], list)

    def test_get_active_notices_no_auth_required(self):
        resp = requests.get(f"{BASE_URL}/api/notices/active", verify=False)
        assert resp.status_code == 200

    def test_active_notices_item_fields(self, created_notice_id):
        resp = SESSION.get(f"{BASE_URL}/api/notices/active")
        items = resp.json().get("items", [])
        if items:
            item = items[0]
            for field in ("id", "content", "is_enabled", "start_time", "end_time", "sort_order"):
                assert field in item, f"Missing field '{field}' in notice item: {item}"


class TestAdminNoticesAPI:
    def test_list_notices_requires_auth(self):
        resp = SESSION.get(f"{BASE_URL}/api/admin/notices")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_list_notices_with_auth(self, admin_headers):
        resp = SESSION.get(f"{BASE_URL}/api/admin/notices", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_create_notice(self, admin_headers):
        now = datetime.utcnow()
        data = {
            "content": "独立创建测试公告",
            "link_url": None,
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "is_enabled": True,
            "sort_order": 99,
        }
        resp = SESSION.post(f"{BASE_URL}/api/admin/notices", json=data, headers=admin_headers)
        assert resp.status_code in (200, 201), f"Create failed: {resp.status_code} {resp.text}"
        result = resp.json()
        assert result.get("id")
        assert result.get("content") == "独立创建测试公告"
        # Cleanup
        SESSION.delete(f"{BASE_URL}/api/admin/notices/{result['id']}", headers=admin_headers)

    def test_create_notice_requires_auth(self):
        now = datetime.utcnow()
        data = {
            "content": "无权限测试",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "is_enabled": True,
            "sort_order": 0,
        }
        resp = SESSION.post(f"{BASE_URL}/api/admin/notices", json=data)
        assert resp.status_code in (401, 403)

    def test_update_notice(self, admin_headers, created_notice_id):
        resp = SESSION.put(
            f"{BASE_URL}/api/admin/notices/{created_notice_id}",
            json={"content": "更新后的公告内容"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Update failed: {resp.status_code} {resp.text}"
        assert resp.json().get("content") == "更新后的公告内容"

    def test_patch_notice_status_disable(self, admin_headers, created_notice_id):
        resp = SESSION.patch(
            f"{BASE_URL}/api/admin/notices/{created_notice_id}/status",
            json={"is_enabled": False},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Patch status failed: {resp.status_code} {resp.text}"
        assert resp.json().get("is_enabled") == False

    def test_patch_notice_status_enable(self, admin_headers, created_notice_id):
        resp = SESSION.patch(
            f"{BASE_URL}/api/admin/notices/{created_notice_id}/status",
            json={"is_enabled": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json().get("is_enabled") == True

    def test_update_nonexistent_notice(self, admin_headers):
        resp = SESSION.put(
            f"{BASE_URL}/api/admin/notices/999999",
            json={"content": "不存在的公告"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_notice(self, admin_headers):
        resp = SESSION.delete(
            f"{BASE_URL}/api/admin/notices/999999",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_delete_notice(self, admin_headers):
        now = datetime.utcnow()
        data = {
            "content": "待删除的公告",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "is_enabled": True,
            "sort_order": 0,
        }
        create_resp = SESSION.post(f"{BASE_URL}/api/admin/notices", json=data, headers=admin_headers)
        assert create_resp.status_code in (200, 201)
        notice_id = create_resp.json()["id"]

        del_resp = SESSION.delete(f"{BASE_URL}/api/admin/notices/{notice_id}", headers=admin_headers)
        assert del_resp.status_code in (200, 204), f"Delete failed: {del_resp.status_code} {del_resp.text}"

    def test_active_notice_appears_in_public_list(self, admin_headers, created_notice_id):
        # Re-enable notice
        SESSION.patch(
            f"{BASE_URL}/api/admin/notices/{created_notice_id}/status",
            json={"is_enabled": True},
            headers=admin_headers,
        )
        resp = SESSION.get(f"{BASE_URL}/api/notices/active")
        items = resp.json().get("items", [])
        ids = [item["id"] for item in items]
        assert created_notice_id in ids, f"Notice {created_notice_id} not found in active list: {ids}"

    def test_disabled_notice_not_in_public_list(self, admin_headers, created_notice_id):
        SESSION.patch(
            f"{BASE_URL}/api/admin/notices/{created_notice_id}/status",
            json={"is_enabled": False},
            headers=admin_headers,
        )
        resp = SESSION.get(f"{BASE_URL}/api/notices/active")
        items = resp.json().get("items", [])
        ids = [item["id"] for item in items]
        assert created_notice_id not in ids, f"Disabled notice {created_notice_id} should not appear in active list"
        # Re-enable for cleanup
        SESSION.patch(
            f"{BASE_URL}/api/admin/notices/{created_notice_id}/status",
            json={"is_enabled": True},
            headers=admin_headers,
        )
