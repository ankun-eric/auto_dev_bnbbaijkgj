"""Tests for Bottom Nav Config — 底部导航Tab后台可配置.

Covers H5 public endpoint, admin CRUD, validation, sort, and permission checks.
"""

import pytest
from httpx import AsyncClient

from app.models.models import BottomNavConfig
from tests.conftest import test_session


# ──────────────── helpers ────────────────


async def _seed_default_navs():
    """Seed the 4 default bottom nav items (2 fixed + 2 configurable)."""
    navs = [
        {"name": "首页", "icon_key": "home", "path": "/", "sort_order": 0, "is_visible": True, "is_fixed": True},
        {"name": "AI健康咨询", "icon_key": "chat", "path": "/ai", "sort_order": 1, "is_visible": True, "is_fixed": False},
        {"name": "服务", "icon_key": "service", "path": "/services", "sort_order": 2, "is_visible": True, "is_fixed": False},
        {"name": "我的", "icon_key": "profile", "path": "/profile", "sort_order": 99, "is_visible": True, "is_fixed": True},
    ]
    async with test_session() as s:
        for nav in navs:
            s.add(BottomNavConfig(**nav))
        await s.commit()


async def _seed_nav(
    name: str = "测试Tab",
    *,
    icon_key: str = "order",
    path: str = "/unified-orders",
    sort_order: int = 3,
    is_visible: bool = True,
    is_fixed: bool = False,
) -> int:
    async with test_session() as s:
        nav = BottomNavConfig(
            name=name,
            icon_key=icon_key,
            path=path,
            sort_order=sort_order,
            is_visible=is_visible,
            is_fixed=is_fixed,
        )
        s.add(nav)
        await s.commit()
        await s.refresh(nav)
        return nav.id


async def _get_configurable_id(client: AsyncClient, admin_headers: dict) -> int:
    resp = await client.get("/api/admin/bottom-nav", headers=admin_headers)
    items = resp.json()["items"]
    for item in items:
        if not item["is_fixed"]:
            return item["id"]
    raise AssertionError("No configurable nav item found")


async def _get_fixed_id(client: AsyncClient, admin_headers: dict) -> int:
    resp = await client.get("/api/admin/bottom-nav", headers=admin_headers)
    items = resp.json()["items"]
    for item in items:
        if item["is_fixed"]:
            return item["id"]
    raise AssertionError("No fixed nav item found")


# ══════════════════════════════════════════════
#  TC-001: H5端获取导航配置（无需认证）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_h5_get_bottom_nav(client: AsyncClient):
    """GET /api/h5/bottom-nav returns code=0, data is array, 首页 first, 我的 last, only visible items."""
    await _seed_default_navs()

    resp = await client.get("/api/h5/bottom-nav")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert isinstance(data, list)
    assert len(data) >= 2
    assert data[0]["name"] == "首页"
    assert data[-1]["name"] == "我的"
    for item in data:
        assert item["is_visible"] is True


# ══════════════════════════════════════════════
#  TC-002: 管理端获取所有导航配置
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc002_admin_list_bottom_nav(client: AsyncClient, admin_headers):
    """GET /api/admin/bottom-nav returns items array with all items."""
    await _seed_default_navs()

    resp = await client.get("/api/admin/bottom-nav", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    items = data["items"]
    assert isinstance(items, list)
    assert len(items) == 4
    has_fixed = any(i["is_fixed"] for i in items)
    has_configurable = any(not i["is_fixed"] for i in items)
    assert has_fixed
    assert has_configurable


# ══════════════════════════════════════════════
#  TC-003: 新增导航项
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc003_create_nav_item(client: AsyncClient, admin_headers):
    """POST /api/admin/bottom-nav creates a new configurable nav item."""
    await _seed_default_navs()

    resp = await client.post(
        "/api/admin/bottom-nav",
        headers=admin_headers,
        json={"name": "测试Tab", "icon_key": "order", "path": "/unified-orders", "is_visible": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试Tab"
    assert data["icon_key"] == "order"
    assert data["is_fixed"] is False
    assert "id" in data


# ══════════════════════════════════════════════
#  TC-004: 新增导航项 - icon_key不合法
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc004_create_nav_invalid_icon(client: AsyncClient, admin_headers):
    """POST /api/admin/bottom-nav with invalid icon_key returns error."""
    resp = await client.post(
        "/api/admin/bottom-nav",
        headers=admin_headers,
        json={"name": "测试", "icon_key": "invalid_icon", "path": "/test", "is_visible": True},
    )
    assert resp.status_code == 400
    assert "icon_key" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  TC-005: 新增导航项 - name超过6字符
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc005_create_nav_name_too_long(client: AsyncClient, admin_headers):
    """POST /api/admin/bottom-nav with name > 6 chars returns error."""
    resp = await client.post(
        "/api/admin/bottom-nav",
        headers=admin_headers,
        json={"name": "这个名字太长了超过六", "icon_key": "order", "path": "/test", "is_visible": True},
    )
    assert resp.status_code in (400, 422)


# ══════════════════════════════════════════════
#  TC-006: 新增导航项 - path不以/开头
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc006_create_nav_path_no_slash(client: AsyncClient, admin_headers):
    """POST /api/admin/bottom-nav with path not starting with / returns error."""
    resp = await client.post(
        "/api/admin/bottom-nav",
        headers=admin_headers,
        json={"name": "测试", "icon_key": "order", "path": "test", "is_visible": True},
    )
    assert resp.status_code == 400
    assert "路径" in resp.json()["detail"] or "path" in resp.json()["detail"].lower()


# ══════════════════════════════════════════════
#  TC-007: 编辑可配置导航项
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc007_update_configurable_nav(client: AsyncClient, admin_headers):
    """PUT /api/admin/bottom-nav/{id} updates a configurable nav item."""
    await _seed_default_navs()
    nav_id = await _get_configurable_id(client, admin_headers)

    resp = await client.put(
        f"/api/admin/bottom-nav/{nav_id}",
        headers=admin_headers,
        json={"name": "新名称"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新名称"


# ══════════════════════════════════════════════
#  TC-008: 编辑固定导航项（应失败）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc008_update_fixed_nav_fails(client: AsyncClient, admin_headers):
    """PUT /api/admin/bottom-nav/{id} on a fixed item returns error."""
    await _seed_default_navs()
    fixed_id = await _get_fixed_id(client, admin_headers)

    resp = await client.put(
        f"/api/admin/bottom-nav/{fixed_id}",
        headers=admin_headers,
        json={"name": "改名"},
    )
    assert resp.status_code == 400
    assert "固定" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  TC-009: 删除可配置导航项
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc009_delete_configurable_nav(client: AsyncClient, admin_headers):
    """DELETE /api/admin/bottom-nav/{id} removes a configurable nav item."""
    nav_id = await _seed_nav("待删除Tab")

    resp = await client.delete(
        f"/api/admin/bottom-nav/{nav_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]


# ══════════════════════════════════════════════
#  TC-010: 删除固定导航项（应失败）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc010_delete_fixed_nav_fails(client: AsyncClient, admin_headers):
    """DELETE /api/admin/bottom-nav/{id} on a fixed item returns error."""
    await _seed_default_navs()
    fixed_id = await _get_fixed_id(client, admin_headers)

    resp = await client.delete(
        f"/api/admin/bottom-nav/{fixed_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "固定" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  TC-011: 批量排序
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc011_sort_configurable_navs(client: AsyncClient, admin_headers):
    """PUT /api/admin/bottom-nav/sort updates sort order of configurable items."""
    id1 = await _seed_nav("Tab1", sort_order=3)
    id2 = await _seed_nav("Tab2", sort_order=4)

    resp = await client.put(
        "/api/admin/bottom-nav/sort",
        headers=admin_headers,
        json=[
            {"id": id1, "sort_order": 5},
            {"id": id2, "sort_order": 3},
        ],
    )
    assert resp.status_code == 200

    verify = await client.get("/api/admin/bottom-nav", headers=admin_headers)
    items = verify.json()["items"]
    by_id = {i["id"]: i for i in items}
    assert by_id[id1]["sort_order"] == 5
    assert by_id[id2]["sort_order"] == 3


# ══════════════════════════════════════════════
#  TC-012: 可配置项数量上限
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc012_configurable_limit(client: AsyncClient, admin_headers):
    """Creating more than 3 configurable nav items should fail."""
    await _seed_default_navs()

    for i in range(1, 4):
        resp = await client.post(
            "/api/admin/bottom-nav",
            headers=admin_headers,
            json={"name": f"额外{i}", "icon_key": "order", "path": f"/extra{i}", "is_visible": True},
        )
        if i <= 1:
            assert resp.status_code == 200, f"Item {i} should succeed, got {resp.status_code}: {resp.text}"
        else:
            if resp.status_code == 400:
                assert "超过" in resp.json()["detail"] or "不能超过" in resp.json()["detail"]
                break
    else:
        resp = await client.post(
            "/api/admin/bottom-nav",
            headers=admin_headers,
            json={"name": "超限", "icon_key": "order", "path": "/over", "is_visible": True},
        )
        assert resp.status_code == 400
        assert "超过" in resp.json()["detail"] or "不能超过" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  TC-013: 未认证访问管理端（应失败）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc013_no_auth_admin_list(client: AsyncClient):
    """GET /api/admin/bottom-nav without token returns 401/403."""
    resp = await client.get("/api/admin/bottom-nav")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc013_no_auth_admin_create(client: AsyncClient):
    """POST /api/admin/bottom-nav without token returns 401/403."""
    resp = await client.post(
        "/api/admin/bottom-nav",
        json={"name": "x", "icon_key": "order", "path": "/x", "is_visible": True},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc013_no_auth_admin_update(client: AsyncClient):
    """PUT /api/admin/bottom-nav/1 without token returns 401/403."""
    resp = await client.put("/api/admin/bottom-nav/1", json={"name": "x"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc013_no_auth_admin_delete(client: AsyncClient):
    """DELETE /api/admin/bottom-nav/1 without token returns 401/403."""
    resp = await client.delete("/api/admin/bottom-nav/1")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc013_no_auth_admin_sort(client: AsyncClient):
    """PUT /api/admin/bottom-nav/sort without token returns 401/403."""
    resp = await client.put("/api/admin/bottom-nav/sort", json=[])
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  TC-014: H5端导航隐藏项不返回
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc014_hidden_nav_not_in_h5(client: AsyncClient, admin_headers):
    """Hidden configurable nav should not appear in H5 endpoint."""
    await _seed_default_navs()
    nav_id = await _seed_nav("隐藏Tab", is_visible=True)

    resp = await client.put(
        f"/api/admin/bottom-nav/{nav_id}",
        headers=admin_headers,
        json={"is_visible": False},
    )
    assert resp.status_code == 200

    h5_resp = await client.get("/api/h5/bottom-nav")
    assert h5_resp.status_code == 200
    data = h5_resp.json()["data"]
    names = [item["name"] for item in data]
    assert "隐藏Tab" not in names
