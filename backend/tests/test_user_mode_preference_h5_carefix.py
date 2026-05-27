"""
[BUG_FIX_CARE_MODE_ENTRY_H5_20260527] 关怀模式入口缺失修复 - 后端接口测试

覆盖：
- GET /api/user/mode-preference 未设置时默认 'standard'
- POST /api/user/mode-preference 写入 'care' 并持久化
- POST /api/user/mode-preference 切换为 'standard' 后再读取
- mode 字段不合法（非 standard / care）时被 422 拒绝
- 未登录时返回 401
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_default_mode_is_standard(client: AsyncClient, auth_headers):
    """新用户首次访问，默认 mode=standard"""
    resp = await client.get("/api/user/mode-preference", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "standard"


@pytest.mark.asyncio
async def test_save_care_mode_persists(client: AsyncClient, auth_headers):
    """POST mode=care 后再 GET 应返回 care"""
    resp = await client.post(
        "/api/user/mode-preference",
        json={"mode": "care"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["mode"] == "care"

    resp2 = await client.get("/api/user/mode-preference", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["mode"] == "care"


@pytest.mark.asyncio
async def test_switch_back_to_standard(client: AsyncClient, auth_headers):
    """先设为 care，再设为 standard，应正确持久化"""
    await client.post(
        "/api/user/mode-preference",
        json={"mode": "care"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/user/mode-preference",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "standard"

    resp2 = await client.get("/api/user/mode-preference", headers=auth_headers)
    assert resp2.json()["mode"] == "standard"


@pytest.mark.asyncio
async def test_invalid_mode_rejected(client: AsyncClient, auth_headers):
    """非法 mode 值应被 422 拒绝"""
    resp = await client.post(
        "/api/user/mode-preference",
        json={"mode": "invalid_mode"},
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_unauthorized_returns_401(client: AsyncClient):
    """未登录访问应返回 401"""
    resp = await client.get("/api/user/mode-preference")
    assert resp.status_code in (401, 403)

    resp2 = await client.post("/api/user/mode-preference", json={"mode": "care"})
    assert resp2.status_code in (401, 403)
