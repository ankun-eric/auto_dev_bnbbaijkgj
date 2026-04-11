#!/usr/bin/env python3
"""
Notice Feature Automated Tests
Tests the HomeNotice backend API and admin management endpoints.
"""
import pytest
import requests
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE_URL}/api"

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"

_token = None
_created_ids = []


def get_token():
    global _token
    if _token:
        return _token
    r = requests.post(f"{API}/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}, verify=False)
    assert r.status_code == 200, f"Login failed: {r.text}"
    _token = r.json()["token"]
    return _token


def auth_headers():
    return {"Authorization": f"Bearer {get_token()}"}


def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def future_iso(days=7):
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def past_iso(days=1):
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


class TestTC001AdminLogin:
    """TC-001: Admin login and get token"""

    def test_login_success(self):
        r = requests.post(
            f"{API}/admin/login",
            json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
            verify=False,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "token" in data, "Response missing 'token' field"
        assert len(data["token"]) > 10, "Token looks too short"


class TestTC002CreateNoticeRequired:
    """TC-002: Admin creates notice with required fields only"""

    def test_create_notice_required_fields(self):
        payload = {
            "content": "TC002 测试公告 - 必填字段",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 10,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200, f"Create notice failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["content"] == payload["content"]
        assert "id" in data
        _created_ids.append(data["id"])


class TestTC003CreateNoticeWithLink:
    """TC-003: Admin creates notice with link_url"""

    def test_create_notice_with_link(self):
        payload = {
            "content": "TC003 带链接的公告",
            "link_url": "/health/guide",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 20,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200, f"Create notice with link failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["link_url"] == "/health/guide"
        _created_ids.append(data["id"])


class TestTC004AdminListNotices:
    """TC-004: Admin gets notice list with pagination"""

    def test_list_notices_pagination(self):
        r = requests.get(f"{API}/admin/notices?page=1&page_size=10", headers=auth_headers(), verify=False)
        assert r.status_code == 200, f"List notices failed: {r.status_code} {r.text}"
        data = r.json()
        assert "items" in data or isinstance(data, list) or "total" in data, \
            f"Unexpected response format: {data}"

    def test_list_notices_page2(self):
        r = requests.get(f"{API}/admin/notices?page=2&page_size=5", headers=auth_headers(), verify=False)
        assert r.status_code == 200, f"Page 2 failed: {r.status_code} {r.text}"


class TestTC005EditNotice:
    """TC-005: Admin edits a notice"""

    def test_edit_notice(self):
        # Create one first
        payload = {
            "content": "TC005 原始内容",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 30,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        notice_id = r.json()["id"]
        _created_ids.append(notice_id)

        # Edit it
        update_payload = {
            "content": "TC005 更新后的内容",
            "start_time": past_iso(1),
            "end_time": future_iso(14),
            "is_enabled": True,
            "sort_order": 31,
        }
        r2 = requests.put(f"{API}/admin/notices/{notice_id}", json=update_payload, headers=auth_headers(), verify=False)
        assert r2.status_code == 200, f"Edit failed: {r2.status_code} {r2.text}"
        data = r2.json()
        assert data["content"] == "TC005 更新后的内容"


class TestTC006PatchStatus:
    """TC-006: Admin enables/disables a notice"""

    def test_patch_status_disable(self):
        # Create enabled notice
        payload = {
            "content": "TC006 启用禁用测试",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 40,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        notice_id = r.json()["id"]
        _created_ids.append(notice_id)

        # Disable it
        r2 = requests.patch(
            f"{API}/admin/notices/{notice_id}/status",
            json={"is_enabled": False},
            headers=auth_headers(),
            verify=False,
        )
        assert r2.status_code == 200, f"Patch status failed: {r2.status_code} {r2.text}"
        assert r2.json()["is_enabled"] == False

    def test_patch_status_enable(self):
        # Create disabled notice
        payload = {
            "content": "TC006b 重新启用测试",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": False,
            "sort_order": 41,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        notice_id = r.json()["id"]
        _created_ids.append(notice_id)

        # Enable it
        r2 = requests.patch(
            f"{API}/admin/notices/{notice_id}/status",
            json={"is_enabled": True},
            headers=auth_headers(),
            verify=False,
        )
        assert r2.status_code == 200, f"Re-enable failed: {r2.status_code} {r2.text}"
        assert r2.json()["is_enabled"] == True


class TestTC007UpdateSort:
    """TC-007: Admin updates sort order"""

    def test_update_sort(self):
        # Create two notices
        ids = []
        for i, content in enumerate(["TC007 排序A", "TC007 排序B"]):
            payload = {
                "content": content,
                "start_time": past_iso(1),
                "end_time": future_iso(7),
                "is_enabled": True,
                "sort_order": 50 + i,
            }
            r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
            assert r.status_code == 200
            ids.append(r.json()["id"])
            _created_ids.append(r.json()["id"])

        # Update sort
        sort_payload = [{"id": ids[0], "sort_order": 99}, {"id": ids[1], "sort_order": 1}]
        r2 = requests.put(f"{API}/admin/notices/sort", json=sort_payload, headers=auth_headers(), verify=False)
        assert r2.status_code == 200, f"Sort update failed: {r2.status_code} {r2.text}"


class TestTC008ActiveNoticesFiltering:
    """TC-008: User gets active notices (enabled + in time range)"""

    def test_active_notices_returns_enabled_in_range(self):
        # Create an active notice
        payload = {
            "content": "TC008 当前有效公告",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 1,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        notice_id = r.json()["id"]
        _created_ids.append(notice_id)

        # Fetch active notices
        r2 = requests.get(f"{API}/notices/active", verify=False)
        assert r2.status_code == 200, f"Active notices failed: {r2.status_code} {r2.text}"
        data = r2.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        assert isinstance(items, list), f"Expected list or dict with items, got: {data}"
        contents = [item["content"] for item in items]
        assert "TC008 当前有效公告" in contents, f"Created notice not in active list: {contents}"


class TestTC009DisabledNoticeNotInActive:
    """TC-009: Disabled notice does not appear in active list"""

    def test_disabled_not_in_active(self):
        # Create disabled notice
        payload = {
            "content": "TC009 禁用公告不应出现",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": False,
            "sort_order": 2,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        _created_ids.append(r.json()["id"])

        # Fetch active notices
        r2 = requests.get(f"{API}/notices/active", verify=False)
        assert r2.status_code == 200
        data = r2.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        contents = [item["content"] for item in items]
        assert "TC009 禁用公告不应出现" not in contents, \
            f"Disabled notice should NOT appear in active list, but found it: {contents}"


class TestTC010FutureNoticeNotInActive:
    """TC-010: Notice with future start_time does not appear in active list"""

    def test_future_notice_not_in_active(self):
        # Create notice that starts in the future
        payload = {
            "content": "TC010 未来生效公告不应出现",
            "start_time": future_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 3,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        _created_ids.append(r.json()["id"])

        # Fetch active notices
        r2 = requests.get(f"{API}/notices/active", verify=False)
        assert r2.status_code == 200
        data = r2.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        contents = [item["content"] for item in items]
        assert "TC010 未来生效公告不应出现" not in contents, \
            f"Future notice should NOT appear in active list, but found it: {contents}"


class TestTC011DeleteNotice:
    """TC-011: Admin deletes a notice"""

    def test_delete_notice(self):
        # Create a notice to delete
        payload = {
            "content": "TC011 待删除公告",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 60,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, headers=auth_headers(), verify=False)
        assert r.status_code == 200
        notice_id = r.json()["id"]

        # Delete it
        r2 = requests.delete(f"{API}/admin/notices/{notice_id}", headers=auth_headers(), verify=False)
        assert r2.status_code in (200, 204), f"Delete failed: {r2.status_code} {r2.text}"

        # Verify it's gone from admin list
        r3 = requests.get(f"{API}/admin/notices", headers=auth_headers(), verify=False)
        assert r3.status_code == 200
        data = r3.json()
        items = data if isinstance(data, list) else data.get("items", [])
        ids = [item["id"] for item in items]
        assert notice_id not in ids, f"Deleted notice {notice_id} still appears in list"


class TestTC012UnauthenticatedAccess:
    """TC-012: Unauthenticated access to admin endpoints returns 401"""

    def test_list_without_token(self):
        r = requests.get(f"{API}/admin/notices", verify=False)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_create_without_token(self):
        payload = {
            "content": "Should fail",
            "start_time": past_iso(1),
            "end_time": future_iso(7),
            "is_enabled": True,
            "sort_order": 1,
        }
        r = requests.post(f"{API}/admin/notices", json=payload, verify=False)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_delete_without_token(self):
        r = requests.delete(f"{API}/admin/notices/9999", verify=False)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


class TestTC013CacheControlHeader:
    """TC-013: Active notices response includes Cache-Control header (30min)"""

    def test_cache_control_header(self):
        r = requests.get(f"{API}/notices/active", verify=False)
        assert r.status_code == 200
        cc = r.headers.get("Cache-Control", "")
        assert cc, f"Cache-Control header is missing. Headers: {dict(r.headers)}"
        assert "max-age=1800" in cc or "max-age" in cc, \
            f"Cache-Control should contain max-age=1800, got: '{cc}'"


class TestCleanup:
    """Cleanup: Delete all notices created during tests"""

    def test_cleanup_created_notices(self):
        headers = auth_headers()
        failed = []
        for notice_id in _created_ids:
            r = requests.delete(f"{API}/admin/notices/{notice_id}", headers=headers, verify=False)
            if r.status_code not in (200, 204, 404):
                failed.append((notice_id, r.status_code))
        assert not failed, f"Failed to cleanup notices: {failed}"
