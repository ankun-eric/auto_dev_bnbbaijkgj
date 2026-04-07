"""拍照识药改版：用户识别历史、管理员对话记录等非 UI API 测试。"""

import pytest
from httpx import AsyncClient

from tests.test_ocr_details import _seed_drug_details


# ──── TC-001 / TC-002：认证 token ────


@pytest.mark.asyncio
async def test_tc001_admin_login_returns_token(client: AsyncClient, admin_token: str):
    """TC-001: 管理员登录获取 token。"""
    assert admin_token
    assert isinstance(admin_token, str)


@pytest.mark.asyncio
async def test_tc002_user_register_login_returns_token(client: AsyncClient, user_token: str):
    """TC-002: 普通用户注册/登录获取 access_token。"""
    assert user_token
    assert isinstance(user_token, str)


# ──── 用户端：GET /api/drug-identify/history ────


@pytest.mark.asyncio
async def test_tc003_drug_identify_history_empty(client: AsyncClient, auth_headers: dict):
    """TC-003: 已登录用户获取识别历史（无数据时为空列表）。"""
    resp = await client.get(
        "/api/drug-identify/history",
        headers=auth_headers,
        params={"page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_tc004_drug_identify_history_unauthorized(client: AsyncClient):
    """TC-004: 未带 token 访问历史接口返回 401。"""
    resp = await client.get("/api/drug-identify/history", params={"page": 1, "page_size": 10})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tc008_drug_identify_history_pagination(client: AsyncClient, auth_headers: dict):
    """TC-008: 分页参数合法时返回 200，结构正确。"""
    resp = await client.get(
        "/api/drug-identify/history",
        headers=auth_headers,
        params={"page": 2, "page_size": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data
    assert isinstance(data["items"], list)


# ──── 管理端：GET /api/admin/drug-details/{id}/conversation ────


@pytest.mark.asyncio
async def test_tc005_admin_drug_detail_conversation(client: AsyncClient, admin_headers: dict):
    """TC-005: 管理员查看某条识药记录的对话（无会话时 messages 可为空）。"""
    await _seed_drug_details(1)
    list_resp = await client.get("/api/admin/drug-details", headers=admin_headers, params={"page": 1, "page_size": 10})
    assert list_resp.status_code == 200
    detail_id = list_resp.json()["items"][0]["id"]

    resp = await client.get(
        f"/api/admin/drug-details/{detail_id}/conversation",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)


@pytest.mark.asyncio
async def test_tc006_admin_drug_detail_conversation_not_found(client: AsyncClient, admin_headers: dict):
    """TC-006: 记录不存在时返回 404。"""
    resp = await client.get("/api/admin/drug-details/99999/conversation", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tc007_admin_drug_detail_conversation_unauthorized(client: AsyncClient):
    """TC-007: 未带 token 访问管理端对话接口返回 401。"""
    resp = await client.get("/api/admin/drug-details/1/conversation")
    assert resp.status_code == 401


# ──── 健康检查 ────


@pytest.mark.asyncio
async def test_tc009_health_check(client: AsyncClient):
    """TC-009: 后端健康检查。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
