"""
Remote server integration tests for SMS login (deployed API).
Uses requests (synchronous) only — no httpx, no app imports.
"""

import time

import urllib3
import pytest
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# pytest 会记录 urllib3 的 InsecureRequestWarning，与 disable_warnings 一并过滤
pytestmark = pytest.mark.filterwarnings(
    "ignore:Unverified HTTPS request:urllib3.exceptions.InsecureRequestWarning"
)

# Project base (HTTPS); API routes are under /api/...
PROJECT_BASE = (
    "https://newbb.test.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
)
API_BASE = f"{PROJECT_BASE}/api"

REQUEST_KW = {"timeout": 30, "verify": False}

# Test phones: server treats 13800138000 / 13800000001 / 13800000002 as test numbers (fixed code 123456, no SMS).
TEST_PHONE_LOGIN = "13800138000"
TEST_PHONE_WRONG = "13800000001"
DEFAULT_ADMIN_PHONE = "13800000000"
DEFAULT_ADMIN_PASSWORD = "admin123"


def _post(path: str, **kwargs):
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    return requests.post(url, **REQUEST_KW, **kwargs)


def _get(path: str, **kwargs):
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    return requests.get(url, **REQUEST_KW, **kwargs)


def _send_sms_code(phone: str, code_type: str = "login"):
    return _post(
        "/auth/sms-code",
        json={"phone": phone, "type": code_type},
    )


def _sms_login(phone: str, code: str):
    return _post(
        "/auth/sms-login",
        json={"phone": phone, "code": code},
    )


class TestServerSmsLogin:
    def test_health_api(self):
        r = _get("/health")
        assert r.status_code == 200, f"GET /api/health expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "ok"

    def test_sms_code_send(self):
        r = _send_sms_code(TEST_PHONE_LOGIN)
        assert r.status_code == 200, f"sms-code failed: {r.status_code} {r.text}"
        body = r.json()
        assert "message" in body or "验证码" in r.text

    def test_sms_login_success(self):
        send = _send_sms_code(TEST_PHONE_LOGIN)
        assert send.status_code == 200, send.text
        login = _sms_login(TEST_PHONE_LOGIN, "123456")
        assert login.status_code == 200, f"SMS login failed: {login.status_code} {login.text}"

    def test_sms_login_wrong_code(self):
        send = _send_sms_code(TEST_PHONE_WRONG)
        assert send.status_code == 200, send.text
        login = _sms_login(TEST_PHONE_WRONG, "654321")
        assert login.status_code == 400, (
            f"wrong code expected 400, got {login.status_code}: {login.text}"
        )
        detail = login.json().get("detail", "")
        assert "验证码无效或已过期" in detail, detail

    def test_sms_login_returns_token(self):
        assert _send_sms_code(TEST_PHONE_LOGIN).status_code == 200
        login = _sms_login(TEST_PHONE_LOGIN, "123456")
        assert login.status_code == 200, login.text
        data = login.json()
        assert "access_token" in data and data["access_token"], data

    def test_sms_login_returns_user_info(self):
        assert _send_sms_code(TEST_PHONE_LOGIN).status_code == 200
        login = _sms_login(TEST_PHONE_LOGIN, "123456")
        assert login.status_code == 200, login.text
        data = login.json()
        assert "user" in data and isinstance(data["user"], dict), data
        u = data["user"]
        assert "id" in u and "phone" in u, u

    def test_password_login_unaffected(self):
        """If default admin exists (init_data), password login should still work."""
        r = _post(
            "/auth/login",
            json={"phone": DEFAULT_ADMIN_PHONE, "password": DEFAULT_ADMIN_PASSWORD},
        )
        if r.status_code == 400:
            detail = (r.json() or {}).get("detail", "")
            if "密码" in detail or "不存在" in detail or "未注册" in detail:
                pytest.skip("服务器上无默认管理员账号或密码已变更，跳过密码登录校验")
        assert r.status_code == 200, f"password login: {r.status_code} {r.text}"
        data = r.json()
        assert "access_token" in data, data
        assert data.get("user", {}).get("phone") == DEFAULT_ADMIN_PHONE

    def test_sms_code_rate_limit(self):
        """Non-test phone: second request within 60s should be 429."""
        suffix = f"{int(time.time()) % 100000000:08d}"
        phone = f"139{suffix}"

        first = _send_sms_code(phone)
        if first.status_code == 500:
            pytest.skip("短信通道不可用，无法验证频率限制（首次发送即失败）")
        assert first.status_code == 200, f"first sms-code: {first.status_code} {first.text}"

        second = _send_sms_code(phone)
        assert second.status_code == 429, (
            f"expected 429 rate limit, got {second.status_code}: {second.text}"
        )
        detail = second.json().get("detail", "")
        assert "发送过于频繁" in detail, detail
