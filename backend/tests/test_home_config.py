"""Tests for Home Config — 首页动态配置与字体切换.

Covers user-facing endpoints (no auth) and admin CRUD for
home config, menus, and banners.
"""

import pytest
from httpx import AsyncClient

from app.models.models import HomeBanner, HomeMenuItem
from tests.conftest import test_session


# ──────────────── helpers ────────────────


async def _seed_menu(
    name: str = "测试菜单",
    *,
    icon_content: str = "💊",
    link_url: str = "/pages/test",
    sort_order: int = 0,
    is_visible: bool = True,
) -> int:
    async with test_session() as s:
        menu = HomeMenuItem(
            name=name,
            icon_type="emoji",
            icon_content=icon_content,
            link_type="internal",
            link_url=link_url,
            sort_order=sort_order,
            is_visible=is_visible,
        )
        s.add(menu)
        await s.commit()
        await s.refresh(menu)
        return menu.id


async def _seed_banner(
    image_url: str = "https://example.com/banner.jpg",
    *,
    sort_order: int = 0,
    is_visible: bool = True,
) -> int:
    async with test_session() as s:
        banner = HomeBanner(
            image_url=image_url,
            link_type="none",
            sort_order=sort_order,
            is_visible=is_visible,
        )
        s.add(banner)
        await s.commit()
        await s.refresh(banner)
        return banner.id


# ══════════════════════════════════════════════
#  TC-001: 获取首页配置（无需登录）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_get_home_config_public(client: AsyncClient):
    """GET /api/home-config returns 200 with all config fields."""
    resp = await client.get("/api/home-config")
    assert resp.status_code == 200
    data = resp.json()
    for field in (
        "search_visible",
        "search_placeholder",
        "grid_columns",
        "font_switch_enabled",
        "font_default_level",
        "font_standard_size",
        "font_large_size",
        "font_xlarge_size",
    ):
        assert field in data, f"missing field: {field}"


# ══════════════════════════════════════════════
#  TC-002: 获取可见菜单（无需登录）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc002_get_visible_menus_public(client: AsyncClient):
    """GET /api/home-menus returns 200 with items array."""
    await _seed_menu("菜单A", sort_order=1)
    await _seed_menu("菜单B", sort_order=2)

    resp = await client.get("/api/home-menus")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2


# ══════════════════════════════════════════════
#  TC-003: 获取可见 Banner（无需登录）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc003_get_visible_banners_public(client: AsyncClient):
    """GET /api/home-banners returns 200 with items array."""
    await _seed_banner("https://example.com/b1.jpg", sort_order=1)
    await _seed_banner("https://example.com/b2.jpg", sort_order=2)

    resp = await client.get("/api/home-banners")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2


# ══════════════════════════════════════════════
#  TC-004: 管理员登录获取 token（由 fixture 覆盖）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc004_admin_login(client: AsyncClient, admin_token):
    """Admin token fixture yields a non-empty token string."""
    assert admin_token
    assert isinstance(admin_token, str)


# ══════════════════════════════════════════════
#  TC-005: 管理员获取首页配置
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc005_admin_get_home_config(client: AsyncClient, admin_headers):
    """GET /api/admin/home-config returns config fields with admin auth."""
    resp = await client.get("/api/admin/home-config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "search_visible" in data
    assert "font_switch_enabled" in data


# ══════════════════════════════════════════════
#  TC-006: 管理员更新首页配置
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc006_admin_update_home_config(client: AsyncClient, admin_headers):
    """PUT /api/admin/home-config updates search_placeholder."""
    new_placeholder = "搜索健康知识..."
    resp = await client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={"search_placeholder": new_placeholder},
    )
    assert resp.status_code == 200

    verify = await client.get("/api/admin/home-config", headers=admin_headers)
    assert verify.json()["search_placeholder"] == new_placeholder


# ══════════════════════════════════════════════
#  TC-007: 管理员获取所有菜单
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc007_admin_list_menus(client: AsyncClient, admin_headers):
    """GET /api/admin/home-menus returns all menus (including hidden)."""
    await _seed_menu("可见菜单", is_visible=True)
    await _seed_menu("隐藏菜单", is_visible=False)

    resp = await client.get("/api/admin/home-menus", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2


# ══════════════════════════════════════════════
#  TC-008: 管理员新增菜单项
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc008_admin_create_menu(client: AsyncClient, admin_headers):
    """POST /api/admin/home-menus creates a menu item."""
    resp = await client.post(
        "/api/admin/home-menus",
        headers=admin_headers,
        json={
            "name": "体检报告",
            "icon_type": "emoji",
            "icon_content": "📋",
            "link_type": "internal",
            "link_url": "/pages/checkup",
            "sort_order": 1,
            "is_visible": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "体检报告"
    assert data["icon_content"] == "📋"
    assert "id" in data


# ══════════════════════════════════════════════
#  TC-009: 管理员编辑菜单项
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc009_admin_update_menu(client: AsyncClient, admin_headers):
    """PUT /api/admin/home-menus/{id} updates menu fields."""
    menu_id = await _seed_menu("待编辑菜单")

    resp = await client.put(
        f"/api/admin/home-menus/{menu_id}",
        headers=admin_headers,
        json={"name": "已编辑菜单", "icon_content": "🏥"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "已编辑菜单"
    assert data["icon_content"] == "🏥"


# ══════════════════════════════════════════════
#  TC-010: 管理员菜单排序
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc010_admin_sort_menus(client: AsyncClient, admin_headers):
    """PUT /api/admin/home-menus/sort updates sort order."""
    id1 = await _seed_menu("菜单1", sort_order=1)
    id2 = await _seed_menu("菜单2", sort_order=2)

    resp = await client.put(
        "/api/admin/home-menus/sort",
        headers=admin_headers,
        json=[
            {"id": id1, "sort_order": 2},
            {"id": id2, "sort_order": 1},
        ],
    )
    assert resp.status_code == 200

    verify = await client.get("/api/admin/home-menus", headers=admin_headers)
    items = verify.json()["items"]
    by_id = {i["id"]: i for i in items}
    assert by_id[id1]["sort_order"] == 2
    assert by_id[id2]["sort_order"] == 1


# ══════════════════════════════════════════════
#  TC-011: 管理员删除菜单项
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc011_admin_delete_menu(client: AsyncClient, admin_headers):
    """DELETE /api/admin/home-menus/{id} removes the menu item."""
    menu_id = await _seed_menu("待删除菜单")

    resp = await client.delete(f"/api/admin/home-menus/{menu_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]

    verify = await client.get("/api/admin/home-menus", headers=admin_headers)
    names = [m["name"] for m in verify.json()["items"]]
    assert "待删除菜单" not in names


# ══════════════════════════════════════════════
#  TC-012: 管理员获取所有 Banner
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc012_admin_list_banners(client: AsyncClient, admin_headers):
    """GET /api/admin/home-banners returns all banners (including hidden)."""
    await _seed_banner("https://example.com/v1.jpg", is_visible=True)
    await _seed_banner("https://example.com/h1.jpg", is_visible=False)

    resp = await client.get("/api/admin/home-banners", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2


# ══════════════════════════════════════════════
#  TC-013: 管理员新增 Banner
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc013_admin_create_banner(client: AsyncClient, admin_headers):
    """POST /api/admin/home-banners creates a banner."""
    resp = await client.post(
        "/api/admin/home-banners",
        headers=admin_headers,
        json={
            "image_url": "https://example.com/new_banner.jpg",
            "link_type": "none",
            "sort_order": 1,
            "is_visible": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["image_url"] == "https://example.com/new_banner.jpg"
    assert "id" in data


# ══════════════════════════════════════════════
#  TC-014: 管理员编辑 Banner
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc014_admin_update_banner(client: AsyncClient, admin_headers):
    """PUT /api/admin/home-banners/{id} updates banner fields."""
    banner_id = await _seed_banner("https://example.com/old.jpg")

    resp = await client.put(
        f"/api/admin/home-banners/{banner_id}",
        headers=admin_headers,
        json={"image_url": "https://example.com/updated.jpg"},
    )
    assert resp.status_code == 200
    assert resp.json()["image_url"] == "https://example.com/updated.jpg"


# ══════════════════════════════════════════════
#  TC-015: 管理员 Banner 排序
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc015_admin_sort_banners(client: AsyncClient, admin_headers):
    """PUT /api/admin/home-banners/sort updates sort order."""
    id1 = await _seed_banner("https://example.com/s1.jpg", sort_order=1)
    id2 = await _seed_banner("https://example.com/s2.jpg", sort_order=2)

    resp = await client.put(
        "/api/admin/home-banners/sort",
        headers=admin_headers,
        json=[
            {"id": id1, "sort_order": 2},
            {"id": id2, "sort_order": 1},
        ],
    )
    assert resp.status_code == 200

    verify = await client.get("/api/admin/home-banners", headers=admin_headers)
    items = verify.json()["items"]
    by_id = {i["id"]: i for i in items}
    assert by_id[id1]["sort_order"] == 2
    assert by_id[id2]["sort_order"] == 1


# ══════════════════════════════════════════════
#  TC-016: 管理员删除 Banner
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc016_admin_delete_banner(client: AsyncClient, admin_headers):
    """DELETE /api/admin/home-banners/{id} removes the banner."""
    banner_id = await _seed_banner("https://example.com/del.jpg")

    resp = await client.delete(f"/api/admin/home-banners/{banner_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]

    verify = await client.get("/api/admin/home-banners", headers=admin_headers)
    urls = [b["image_url"] for b in verify.json()["items"]]
    assert "https://example.com/del.jpg" not in urls


# ══════════════════════════════════════════════
#  TC-017: 无权限访问管理端返回 401
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc017_no_auth_admin_home_config(client: AsyncClient):
    resp = await client.get("/api/admin/home-config")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc017_no_auth_admin_update_config(client: AsyncClient):
    resp = await client.put("/api/admin/home-config", json={"search_placeholder": "x"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc017_no_auth_admin_menus(client: AsyncClient):
    resp = await client.get("/api/admin/home-menus")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc017_no_auth_admin_create_menu(client: AsyncClient):
    resp = await client.post("/api/admin/home-menus", json={"name": "x", "icon_content": "x", "link_url": "x"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc017_no_auth_admin_banners(client: AsyncClient):
    resp = await client.get("/api/admin/home-banners")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc017_no_auth_admin_create_banner(client: AsyncClient):
    resp = await client.post("/api/admin/home-banners", json={"image_url": "x"})
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  TC-018: 菜单显示隐藏 — 隐藏菜单用户端不可见
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc018_hidden_menu_not_in_public(client: AsyncClient):
    """Hidden menu should not appear in public endpoint."""
    await _seed_menu("可见菜单", is_visible=True)
    await _seed_menu("隐藏菜单", is_visible=False)

    resp = await client.get("/api/home-menus")
    assert resp.status_code == 200
    items = resp.json()["items"]
    names = [m["name"] for m in items]
    assert "可见菜单" in names
    assert "隐藏菜单" not in names


# ══════════════════════════════════════════════
#  TC-019: Banner 显示隐藏 — 隐藏 Banner 用户端不可见
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc019_hidden_banner_not_in_public(client: AsyncClient):
    """Hidden banner should not appear in public endpoint."""
    await _seed_banner("https://example.com/visible.jpg", is_visible=True)
    await _seed_banner("https://example.com/hidden.jpg", is_visible=False)

    resp = await client.get("/api/home-banners")
    assert resp.status_code == 200
    items = resp.json()["items"]
    urls = [b["image_url"] for b in items]
    assert "https://example.com/visible.jpg" in urls
    assert "https://example.com/hidden.jpg" not in urls


# ══════════════════════════════════════════════
#  TC-020: 字体配置更新验证 — 更新后用户端能获取新值
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc020_font_config_update_reflected(client: AsyncClient, admin_headers):
    """After admin updates font config, public endpoint reflects changes."""
    resp = await client.put(
        "/api/admin/home-config",
        headers=admin_headers,
        json={
            "font_switch_enabled": False,
            "font_default_level": "large",
            "font_standard_size": 16,
            "font_large_size": 20,
            "font_xlarge_size": 24,
        },
    )
    assert resp.status_code == 200

    public = await client.get("/api/home-config")
    assert public.status_code == 200
    data = public.json()
    assert data["font_switch_enabled"] is False
    assert data["font_default_level"] == "large"
    assert data["font_standard_size"] == 16
    assert data["font_large_size"] == 20
    assert data["font_xlarge_size"] == 24
