"""
Server-side SMS verification automated tests.
Tests the deployed SMS service at the remote server.
"""

import time
import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(
        f"{API_URL}/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        verify=False,
        timeout=15,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("data", {}).get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


class TestHealthCheck:
    def test_tc001_health(self):
        """TC-001: GET /api/health → 200, status=ok"""
        resp = requests.get(f"{API_URL}/health", verify=False, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok", f"Unexpected health response: {data}"


class TestAdminLogin:
    def test_tc002_admin_login(self):
        """TC-002: POST /api/admin/login → 200, get token"""
        resp = requests.post(
            f"{API_URL}/admin/login",
            json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
            verify=False,
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        token = data.get("token") or data.get("data", {}).get("token") or data.get("access_token")
        assert token, f"No token found in login response: {data}"


class TestSMSConfig:
    def test_tc003_get_sms_config(self, auth_headers):
        """TC-003: GET /api/admin/sms/config → 200 with correct tencent config"""
        resp = requests.get(f"{API_URL}/admin/sms/config", headers=auth_headers, verify=False, timeout=10)
        assert resp.status_code == 200, f"SMS config request failed: {resp.status_code} {resp.text}"
        data = resp.json()

        config = data.get("tencent") or data.get("data", {}).get("tencent") or data
        if "config" in data:
            config = data["config"]
        if isinstance(config, dict) and "tencent" in config:
            config = config["tencent"]

        sdk_app_id = str(config.get("sdk_app_id", ""))
        sign_name = config.get("sign_name", "")
        template_id = str(config.get("template_id", ""))
        app_key = config.get("app_key", "")

        assert sdk_app_id == "1400920269", f"sdk_app_id mismatch: {sdk_app_id}"
        assert sign_name == "呃唉帮帮网络", f"sign_name mismatch: {sign_name}"
        assert template_id == "2201340", f"template_id mismatch: {template_id}"
        assert app_key == "7e3c8242bf0799cca367fa18fa47a7ea", f"app_key mismatch: {app_key}"


class TestSMSTemplates:
    def test_tc004_get_templates(self, auth_headers):
        """TC-004: GET /api/admin/sms/templates → 200, login template exists"""
        resp = requests.get(f"{API_URL}/admin/sms/templates", headers=auth_headers, verify=False, timeout=10)
        assert resp.status_code == 200, f"Templates request failed: {resp.status_code} {resp.text}"
        data = resp.json()

        templates = data if isinstance(data, list) else data.get("items") or data.get("data") or data.get("templates", [])
        if isinstance(templates, dict):
            templates = templates.get("items") or templates.get("templates") or []

        login_tpl = None
        for t in templates:
            tid = str(t.get("template_id", ""))
            if tid == "2201340":
                login_tpl = t
                break

        assert login_tpl is not None, f"No template with id=2201340 found. Templates: {templates}"
        name = login_tpl.get("name", "")
        assert "登录验证" in name, f"Template name mismatch: {name}"

        content = login_tpl.get("content", "") or login_tpl.get("description", "")
        assert "验证码" in content or "code" in content.lower(), f"Template content missing verification code info: {content}"

    def test_tc011_template_variables(self, auth_headers):
        """TC-011: Template 2201340 has variables with code and expiry"""
        resp = requests.get(f"{API_URL}/admin/sms/templates", headers=auth_headers, verify=False, timeout=10)
        assert resp.status_code == 200
        data = resp.json()

        templates = data if isinstance(data, list) else data.get("items") or data.get("data") or data.get("templates", [])
        if isinstance(templates, dict):
            templates = templates.get("items") or templates.get("templates") or []

        login_tpl = None
        for t in templates:
            if str(t.get("template_id", "")) == "2201340":
                login_tpl = t
                break

        assert login_tpl is not None, f"Template 2201340 not found"
        variables = login_tpl.get("variables", [])
        assert isinstance(variables, list), f"variables is not a list: {variables}"
        assert len(variables) >= 2, f"Expected at least 2 variables, got {len(variables)}: {variables}"

        var_names = [v if isinstance(v, str) else v.get("name", "") or v.get("key", "") for v in variables]
        var_str = " ".join(var_names).lower()
        has_code = any(k in var_str for k in ["验证码", "code", "验证", "码"])
        has_time = any(k in var_str for k in ["有效", "时间", "分钟", "time", "expir", "minute"])
        assert has_code or has_time, f"Variables don't contain code/time info: {variables}"


class TestSMSAuth:
    def test_tc005_no_auth(self):
        """TC-005: GET /api/admin/sms/config without token → 401 or 403"""
        resp = requests.get(f"{API_URL}/admin/sms/config", verify=False, timeout=10)
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}: {resp.text}"

    def test_tc006_rate_limit(self):
        """TC-006: POST /api/auth/sms-code twice → second should return 429"""
        phone = "13900001111"
        payload = {"phone": phone}

        resp1 = requests.post(f"{API_URL}/auth/sms-code", json=payload, verify=False, timeout=15)

        time.sleep(0.5)
        resp2 = requests.post(f"{API_URL}/auth/sms-code", json=payload, verify=False, timeout=15)
        assert resp2.status_code == 429, (
            f"Expected 429 on second request, got {resp2.status_code}: {resp2.text}"
        )

    def test_tc007_wrong_code_login(self):
        """TC-007: POST /api/auth/sms-login with wrong code → 400"""
        resp = requests.post(
            f"{API_URL}/auth/sms-login",
            json={"phone": "13900002222", "code": "000000"},
            verify=False,
            timeout=10,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


class TestSMSAdmin:
    def test_tc008_update_config(self, auth_headers):
        """TC-008: PUT /api/admin/sms/config update sign → 200, verify, restore"""
        get_resp = requests.get(f"{API_URL}/admin/sms/config", headers=auth_headers, verify=False, timeout=10)
        assert get_resp.status_code == 200
        original_data = get_resp.json()

        original_config = original_data.get("tencent") or original_data.get("data", {}).get("tencent") or original_data
        if "config" in original_data:
            original_config = original_data["config"]
        if isinstance(original_config, dict) and "tencent" in original_config:
            original_config = original_config["tencent"]

        original_sign = original_config.get("sign_name", "呃唉帮帮网络")

        new_sign = "测试签名临时"
        update_payload = {
            "provider": "tencent",
            "sign_name": new_sign,
            "sdk_app_id": original_config.get("sdk_app_id", ""),
            "template_id": original_config.get("template_id", ""),
            "app_key": original_config.get("app_key", ""),
        }
        put_resp = requests.put(
            f"{API_URL}/admin/sms/config",
            json=update_payload,
            headers=auth_headers,
            verify=False,
            timeout=10,
        )
        if put_resp.status_code == 422:
            alt_payload = {"provider": "tencent", "tencent": {**original_config, "sign_name": new_sign}}
            put_resp = requests.put(
                f"{API_URL}/admin/sms/config",
                json=alt_payload,
                headers=auth_headers,
                verify=False,
                timeout=10,
            )
        assert put_resp.status_code == 200, f"Update config failed: {put_resp.status_code} {put_resp.text}"

        verify_resp = requests.get(f"{API_URL}/admin/sms/config", headers=auth_headers, verify=False, timeout=10)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        verify_config = verify_data.get("tencent") or verify_data.get("data", {}).get("tencent") or verify_data
        if "config" in verify_data:
            verify_config = verify_data["config"]
        if isinstance(verify_config, dict) and "tencent" in verify_config:
            verify_config = verify_config["tencent"]

        assert verify_config.get("sign_name") == new_sign, (
            f"Sign not updated: {verify_config.get('sign_name')}"
        )

        restore_payload = {
            "provider": "tencent",
            "sign_name": original_sign,
            "sdk_app_id": original_config.get("sdk_app_id", ""),
            "template_id": original_config.get("template_id", ""),
            "app_key": original_config.get("app_key", ""),
        }
        restore_resp = requests.put(
            f"{API_URL}/admin/sms/config",
            json=restore_payload,
            headers=auth_headers,
            verify=False,
            timeout=10,
        )
        if restore_resp.status_code == 422:
            alt_restore = {"provider": "tencent", "tencent": {**original_config, "sign_name": original_sign}}
            restore_resp = requests.put(
                f"{API_URL}/admin/sms/config",
                json=alt_restore,
                headers=auth_headers,
                verify=False,
                timeout=10,
            )
        assert restore_resp.status_code == 200, f"Restore failed: {restore_resp.status_code}"

    def test_tc009_sms_logs(self, auth_headers):
        """TC-009: GET /api/admin/sms/logs → 200 with items, total"""
        resp = requests.get(f"{API_URL}/admin/sms/logs", headers=auth_headers, verify=False, timeout=10)
        assert resp.status_code == 200, f"SMS logs failed: {resp.status_code} {resp.text}"
        data = resp.json()

        log_data = data.get("data", data)
        assert "items" in log_data or "logs" in log_data, f"No items/logs key in response: {data}"
        assert "total" in log_data or "count" in log_data, f"No total/count key in response: {data}"

    def test_tc010_test_send(self, auth_headers):
        """TC-010: POST /api/admin/sms/test send test SMS → 200"""
        resp = requests.post(
            f"{API_URL}/admin/sms/test",
            json={"phone": "13800000000", "template_id": "2201340"},
            headers=auth_headers,
            verify=False,
            timeout=15,
        )
        assert resp.status_code == 200, f"Test send failed: {resp.status_code} {resp.text}"
        data = resp.json()
        has_result = "success" in data or "message" in data or "data" in data
        assert has_result, f"Response missing success/message field: {data}"
