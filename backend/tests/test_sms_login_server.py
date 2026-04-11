"""
Remote server integration tests for SMS login bug fix.
Targets the deployed API at the configured BASE_URL.
Uses requests (synchronous) — no project imports.
"""

import requests
import pytest

BASE_URL = (
    "https://newbb.test.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
)


class TestCorrectCodeLogin:
    """用例 1: 正确验证码登录应成功"""

    def test_sms_login_with_correct_code(self):
        # Step 1: 发送验证码
        resp = requests.post(
            f"{BASE_URL}/auth/sms-code",
            json={"phone": "13800138000", "type": "login"},
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"发送验证码失败: status={resp.status_code}, body={resp.text}"
        )

        # Step 2: 使用正确验证码登录
        login_resp = requests.post(
            f"{BASE_URL}/auth/sms-login",
            json={"phone": "13800138000", "code": "123456"},
            timeout=15,
        )
        assert login_resp.status_code == 200, (
            f"正确验证码登录失败: status={login_resp.status_code}, body={login_resp.text}"
        )
        data = login_resp.json()
        assert "access_token" in data, (
            f"响应中缺少 access_token, 响应内容: {data}"
        )


class TestWrongCodeLogin:
    """用例 2: 错误验证码登录应失败"""

    def test_sms_login_with_wrong_code(self):
        # Step 1: 发送验证码
        resp = requests.post(
            f"{BASE_URL}/auth/sms-code",
            json={"phone": "13800000001", "type": "login"},
            timeout=15,
        )
        assert resp.status_code == 200, (
            f"发送验证码失败: status={resp.status_code}, body={resp.text}"
        )

        # Step 2: 使用错误验证码登录
        login_resp = requests.post(
            f"{BASE_URL}/auth/sms-login",
            json={"phone": "13800000001", "code": "654321"},
            timeout=15,
        )
        assert login_resp.status_code == 400, (
            f"期望 400, 实际: status={login_resp.status_code}, body={login_resp.text}"
        )
        detail = login_resp.json().get("detail", "")
        assert "验证码无效或已过期" in detail, (
            f"期望 detail 包含 '验证码无效或已过期', 实际: {detail}"
        )


class TestRateLimit:
    """用例 3: 频率限制测试

    注意：服务端代码对 TEST_PHONES (13800138000, 13800000001, 13800000002)
    跳过了频率限制检查，因此使用一个非测试手机号来验证频率限制逻辑。
    非测试手机号会触发真实短信发送，可能返回 500（短信服务不可用），
    但只要第二次请求返回 429 就说明频率限制生效。
    如果第一次就返回 500（短信失败且未插入记录），则跳过本用例。
    """

    def test_sms_code_rate_limit(self):
        phone = "13900990099"

        first = requests.post(
            f"{BASE_URL}/auth/sms-code",
            json={"phone": phone, "type": "login"},
            timeout=15,
        )
        if first.status_code == 500:
            pytest.skip(
                "短信服务不可用，无法验证频率限制（非测试号首次发送失败）"
            )
        assert first.status_code == 200, (
            f"第一次发送验证码失败: status={first.status_code}, body={first.text}"
        )

        second = requests.post(
            f"{BASE_URL}/auth/sms-code",
            json={"phone": phone, "type": "login"},
            timeout=15,
        )
        assert second.status_code == 429, (
            f"期望 429 频率限制, 实际: status={second.status_code}, body={second.text}"
        )
        detail = second.json().get("detail", "")
        assert "发送过于频繁" in detail, (
            f"期望 detail 包含 '发送过于频繁', 实际: {detail}"
        )


class TestPasswordLogin:
    """用例 4: 密码登录不受影响"""

    def test_password_login_no_500(self):
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"phone": "admin", "password": "admin123"},
            timeout=15,
        )
        assert resp.status_code != 500, (
            f"密码登录接口返回 500 服务器错误: body={resp.text}"
        )
        assert resp.status_code in (200, 400), (
            f"期望 200 或 400, 实际: status={resp.status_code}, body={resp.text}"
        )
