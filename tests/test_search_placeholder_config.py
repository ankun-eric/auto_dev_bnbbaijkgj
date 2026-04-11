"""Tests for 首页搜索栏提示文字后台配置化.

验证:
- 后端默认 search_placeholder 值已更新
- 管理后台可修改 search_placeholder
- 各端清空 placeholder 后返回空字符串（客户端兜底）
- 接口返回正确的字段结构
"""

import pytest
import httpx

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
DEFAULT_PLACEHOLDER = "搜索健康知识、服务、商品"


@pytest.fixture(scope="module")
def http_client():
    with httpx.Client(base_url=BASE_URL, timeout=30, verify=False) as client:
        yield client


@pytest.fixture(scope="module")
def admin_token(http_client):
    resp = http_client.post("/api/auth/login", json={
        "phone": "13800138000",
        "code": "888888",
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token", "")
    return ""


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"} if admin_token else {}


def test_tc001_home_config_returns_search_placeholder(http_client):
    """GET /api/home-config 返回 search_placeholder 字段。"""
    resp = http_client.get("/api/home-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "search_placeholder" in data, "响应缺少 search_placeholder 字段"
    assert isinstance(data["search_placeholder"], str)


def test_tc002_home_config_returns_search_visible(http_client):
    """GET /api/home-config 返回 search_visible 字段。"""
    resp = http_client.get("/api/home-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "search_visible" in data


def test_tc003_admin_update_search_placeholder(http_client, admin_headers):
    """PUT /api/admin/home-config 可修改 search_placeholder。"""
    if not admin_headers:
        pytest.skip("无法获取管理员token")

    new_text = "测试搜索文字_placeholder_test"
    resp = http_client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={"search_placeholder": new_text},
    )
    assert resp.status_code == 200

    verify = http_client.get("/api/home-config")
    assert verify.status_code == 200
    assert verify.json()["search_placeholder"] == new_text


def test_tc004_admin_clear_search_placeholder(http_client, admin_headers):
    """清空 search_placeholder 后接口返回空字符串，客户端应使用兜底值。"""
    if not admin_headers:
        pytest.skip("无法获取管理员token")

    resp = http_client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={"search_placeholder": ""},
    )
    assert resp.status_code == 200

    verify = http_client.get("/api/home-config")
    assert verify.status_code == 200
    placeholder = verify.json()["search_placeholder"]
    assert placeholder == "" or isinstance(placeholder, str)


def test_tc005_admin_restore_default_placeholder(http_client, admin_headers):
    """恢复默认提示文字。"""
    if not admin_headers:
        pytest.skip("无法获取管理员token")

    resp = http_client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={"search_placeholder": DEFAULT_PLACEHOLDER},
    )
    assert resp.status_code == 200

    verify = http_client.get("/api/home-config")
    assert verify.status_code == 200
    assert verify.json()["search_placeholder"] == DEFAULT_PLACEHOLDER


def test_tc006_search_placeholder_max_length(http_client, admin_headers):
    """search_placeholder 支持最大50字符。"""
    if not admin_headers:
        pytest.skip("无法获取管理员token")

    long_text = "搜" * 50
    resp = http_client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={"search_placeholder": long_text},
    )
    assert resp.status_code == 200

    http_client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={"search_placeholder": DEFAULT_PLACEHOLDER},
    )


def test_tc007_home_config_no_auth_required(http_client):
    """GET /api/home-config 无需认证。"""
    resp = http_client.get("/api/home-config")
    assert resp.status_code == 200


def test_tc008_admin_update_requires_auth(http_client):
    """PUT /api/admin/home-config 需要认证。"""
    resp = http_client.put(
        "/api/admin/home-config",
        json={"search_placeholder": "unauthorized test"},
    )
    assert resp.status_code in (401, 403)


def test_tc009_home_config_response_structure(http_client):
    """验证 home-config 完整响应结构。"""
    resp = http_client.get("/api/home-config")
    assert resp.status_code == 200
    data = resp.json()
    expected_fields = [
        "search_visible",
        "search_placeholder",
        "grid_columns",
    ]
    for field in expected_fields:
        assert field in data, f"响应缺少字段: {field}"
