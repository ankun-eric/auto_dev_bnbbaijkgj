"""
Server-side automated tests for AI Config Quick Test feature.
Target: https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""

import warnings
import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="session")
def admin_token():
    resp = requests.post(
        f"{BASE_URL}/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        verify=False,
        timeout=15,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- TC-001 ----------
class TestTC001ListNewFields:
    def test_list_returns_new_fields(self, auth_headers):
        """TC-001: GET /api/admin/ai-config returns last_test_status, last_test_time, last_test_message"""
        resp = requests.get(
            f"{BASE_URL}/admin/ai-config",
            headers=auth_headers,
            verify=False,
            timeout=15,
        )
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
        body = resp.json()

        items = None
        if isinstance(body.get("data"), dict):
            items = body["data"].get("items")
        elif isinstance(body.get("data"), list):
            items = body["data"]
        elif isinstance(body.get("items"), list):
            items = body["items"]
        else:
            items = body.get("data", [])

        assert isinstance(items, list), f"items is not a list: {type(items)}, body={body}"

        for item in items:
            assert "last_test_status" in item, f"Missing last_test_status in item: {item}"
            assert "last_test_time" in item, f"Missing last_test_time in item: {item}"
            assert "last_test_message" in item, f"Missing last_test_message in item: {item}"


# ---------- TC-002 ----------
class TestTC002MissingParams:
    def test_missing_params(self, auth_headers):
        """TC-002: POST /api/admin/ai-config/test with {} should return error"""
        resp = requests.post(
            f"{BASE_URL}/admin/ai-config/test",
            json={},
            headers=auth_headers,
            verify=False,
            timeout=30,
        )
        assert resp.status_code < 500, f"Got 500 server error: {resp.text}"
        body = resp.json()

        success = body.get("success")
        error_detail = body.get("error_detail", "")
        has_error = (success is False) or (resp.status_code >= 400) or bool(error_detail)
        assert has_error, f"Expected error but got: status={resp.status_code} body={body}"


# ---------- TC-003 ----------
class TestTC003NonExistentConfigId:
    def test_non_existent_config_id(self, auth_headers):
        """TC-003: POST /api/admin/ai-config/test with config_id=99999 should return 404"""
        resp = requests.post(
            f"{BASE_URL}/admin/ai-config/test",
            json={"config_id": 99999},
            headers=auth_headers,
            verify=False,
            timeout=30,
        )
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"


# ---------- TC-004 ----------
class TestTC004InvalidUrl:
    def test_invalid_url(self, auth_headers):
        """TC-004: POST /api/admin/ai-config/test with invalid base_url should return success=false"""
        resp = requests.post(
            f"{BASE_URL}/admin/ai-config/test",
            json={
                "base_url": "http://invalid-host-that-does-not-exist.example.com/v1",
                "model_name": "test",
                "api_key": "test-key",
            },
            headers=auth_headers,
            verify=False,
            timeout=60,
        )
        assert resp.status_code < 500, f"Got server error {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("success") is False, f"Expected success=false, got: {body}"
        assert body.get("error_detail"), f"Expected non-empty error_detail, got: {body}"


# ---------- TC-005 ----------
class TestTC005CustomTestMessage:
    def test_custom_test_message(self, auth_headers):
        """TC-005: POST /api/admin/ai-config/test with test_message should not 500"""
        resp = requests.post(
            f"{BASE_URL}/admin/ai-config/test",
            json={
                "base_url": "http://invalid-host.example.com/v1",
                "model_name": "test",
                "api_key": "test-key",
                "test_message": "自定义消息",
            },
            headers=auth_headers,
            verify=False,
            timeout=60,
        )
        assert resp.status_code < 500, f"Got server error {resp.status_code}: {resp.text}"


# ---------- TC-006 ----------
class TestTC006ExistingConfigTest:
    def test_existing_config(self, auth_headers):
        """TC-006: Test with existing config_id, then verify last_test fields updated"""
        resp = requests.get(
            f"{BASE_URL}/admin/ai-config",
            headers=auth_headers,
            verify=False,
            timeout=15,
        )
        assert resp.status_code == 200
        body = resp.json()

        items = None
        if isinstance(body.get("data"), dict):
            items = body["data"].get("items")
        elif isinstance(body.get("data"), list):
            items = body["data"]
        elif isinstance(body.get("items"), list):
            items = body["items"]
        else:
            items = body.get("data", [])

        if not items:
            pytest.skip("No AI configs available to test")

        config_id = items[0].get("id")
        assert config_id is not None, f"First config has no id: {items[0]}"

        test_resp = requests.post(
            f"{BASE_URL}/admin/ai-config/test",
            json={"config_id": config_id, "test_message": "你好"},
            headers=auth_headers,
            verify=False,
            timeout=60,
        )
        assert test_resp.status_code < 500, f"Got server error {test_resp.status_code}: {test_resp.text}"
        test_body = test_resp.json()
        assert "success" in test_body, f"Missing 'success' field: {test_body}"
        assert "response_time" in test_body, f"Missing 'response_time' field: {test_body}"

        list_resp2 = requests.get(
            f"{BASE_URL}/admin/ai-config",
            headers=auth_headers,
            verify=False,
            timeout=15,
        )
        assert list_resp2.status_code == 200
        body2 = list_resp2.json()

        items2 = None
        if isinstance(body2.get("data"), dict):
            items2 = body2["data"].get("items")
        elif isinstance(body2.get("data"), list):
            items2 = body2["data"]
        elif isinstance(body2.get("items"), list):
            items2 = body2["items"]
        else:
            items2 = body2.get("data", [])

        target = None
        for item in items2:
            if item.get("id") == config_id:
                target = item
                break
        assert target is not None, f"Config {config_id} not found in second list call"
        assert target.get("last_test_status") is not None, (
            f"last_test_status is still null after test for config {config_id}: {target}"
        )
        assert target.get("last_test_time") is not None, (
            f"last_test_time is still null after test for config {config_id}: {target}"
        )
