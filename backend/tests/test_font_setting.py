import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# TC-001: 未设置字体的用户获取默认值为 standard
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_font_setting_default(client: AsyncClient, auth_headers):
    response = await client.get("/api/user/font-setting", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["font_size_level"] == "standard"


# ---------------------------------------------------------------------------
# TC-002: 用户更新字体为 large，返回成功
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_font_setting_large(client: AsyncClient, auth_headers):
    response = await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "large"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["font_size_level"] == "large"


# ---------------------------------------------------------------------------
# TC-003: 用户更新字体为 extra_large，返回成功
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_font_setting_extra_large(client: AsyncClient, auth_headers):
    response = await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "extra_large"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["font_size_level"] == "extra_large"


# ---------------------------------------------------------------------------
# TC-004: 更新后再获取，返回更新后的值
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_font_setting_after_update(client: AsyncClient, auth_headers):
    await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "large"},
        headers=auth_headers,
    )

    response = await client.get("/api/user/font-setting", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["font_size_level"] == "large"


# ---------------------------------------------------------------------------
# TC-005: 用户更新字体回 standard，返回成功
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_font_setting_back_to_standard(client: AsyncClient, auth_headers):
    await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "extra_large"},
        headers=auth_headers,
    )

    response = await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "standard"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["font_size_level"] == "standard"


# ---------------------------------------------------------------------------
# TC-006: 未登录用户访问 GET 返回 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_font_setting_unauthorized(client: AsyncClient):
    response = await client.get("/api/user/font-setting")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# TC-007: 未登录用户访问 PUT 返回 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_font_setting_unauthorized(client: AsyncClient):
    response = await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "large"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# TC-008: PUT 无效的 font_size_level 值返回 422
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_font_setting_invalid_value(client: AsyncClient, auth_headers):
    response = await client.put(
        "/api/user/font-setting",
        json={"font_size_level": "huge"},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# TC-009: PUT 缺少 font_size_level 字段返回 422
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_font_setting_missing_field(client: AsyncClient, auth_headers):
    response = await client.put(
        "/api/user/font-setting",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# TC-010: 多次连续更新，最终读取为最后一次更新的值
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multiple_updates_returns_last_value(client: AsyncClient, auth_headers):
    for level in ["large", "extra_large", "standard", "large", "extra_large"]:
        resp = await client.put(
            "/api/user/font-setting",
            json={"font_size_level": level},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    response = await client.get("/api/user/font-setting", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["font_size_level"] == "extra_large"
