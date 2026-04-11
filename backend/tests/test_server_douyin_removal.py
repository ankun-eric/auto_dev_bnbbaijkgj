"""
非 UI 自动化测试：验证已部署环境已移除抖音授权登录相关接口与页面内容。

默认针对部署 URL；可通过环境变量 SERVER_BASE_URL 覆盖。
HTTPS 请求使用 verify=False 以兼容自签或证书链问题。
"""

from __future__ import annotations

import os

import httpx
import pytest

DEFAULT_BASE = (
    "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
)

REQUIRED_REGISTER_KEYS = (
    "enable_self_registration",
    "wechat_register_mode",
    "register_page_layout",
    "show_profile_completion_prompt",
    "member_card_no_rule",
)

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


def _base_url() -> str:
    return os.environ.get("SERVER_BASE_URL", DEFAULT_BASE).rstrip("/")


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(verify=False, timeout=30.0, follow_redirects=True) as c:
        yield c


def test_tc001_register_settings_no_douyin_field(client: httpx.Client):
    """TC-001: GET /api/auth/register-settings 不含 douyin_register_mode，且保留其它字段。"""
    r = client.get(f"{_base_url()}/api/auth/register-settings")
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:500]}"
    data = r.json()
    assert "douyin_register_mode" not in data, "响应仍包含 douyin_register_mode"
    for key in REQUIRED_REGISTER_KEYS:
        assert key in data, f"缺少字段: {key}"


def test_tc002_admin_register_settings_no_douyin_field(client: httpx.Client):
    """TC-002: 管理员 GET /api/admin/settings/register 不含 douyin_register_mode。"""
    login = client.post(
        f"{_base_url()}/api/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert token
    r = client.get(
        f"{_base_url()}/api/admin/settings/register",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert "douyin_register_mode" not in r.json(), "管理端注册设置仍包含 douyin_register_mode"


def test_tc003_admin_save_ignores_douyin_updates_wechat(client: httpx.Client):
    """TC-003: POST 可带 douyin_register_mode 但被忽略；返回无 douyin；wechat 更新生效。"""
    login = client.post(
        f"{_base_url()}/api/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"{_base_url()}/api/admin/settings/register",
        headers=headers,
        json={
            "douyin_register_mode": "fill_profile",
            "wechat_register_mode": "fill_profile",
        },
    )
    assert r.status_code == 200, f"status={r.status_code} body={r.text}"
    body = r.json()
    settings = body.get("settings") or {}
    assert "douyin_register_mode" not in settings, "返回的 settings 仍含 douyin_register_mode"
    assert settings.get("wechat_register_mode") == "fill_profile"


def test_tc004_h5_html_no_douyin_text(client: httpx.Client):
    """TC-004: H5 根路径 HTML 不含「抖音」或 douyin（大小写不敏感）。"""
    r = client.get(f"{_base_url()}/")
    assert r.status_code == 200, r.text[:500]
    text = r.text
    assert "抖音" not in text
    assert "douyin" not in text.lower()


def test_tc005_admin_html_no_douyin_text(client: httpx.Client):
    """TC-005: 管理后台 HTML 不含「抖音」或 douyin（大小写不敏感）。"""
    r = client.get(f"{_base_url()}/admin/")
    assert r.status_code == 200, r.text[:500]
    text = r.text
    assert "抖音" not in text
    assert "douyin" not in text.lower()


def test_tc006_health_ok(client: httpx.Client):
    """TC-006: GET /api/health 返回 200。"""
    r = client.get(f"{_base_url()}/api/health")
    assert r.status_code == 200, r.text
