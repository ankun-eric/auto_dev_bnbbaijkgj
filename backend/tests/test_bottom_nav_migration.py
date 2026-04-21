"""Tests for bottom_nav_migration: /orders -> /unified-orders 幂等迁移."""
import pytest

from app.models.models import BottomNavConfig
from app.services.bottom_nav_migration import migrate_bottom_nav_order_path
from tests.conftest import test_session


@pytest.mark.asyncio
async def test_migrate_order_path_rewrites_matching_rows():
    """匹配 path=/orders 且 name 为订单相关命名的记录应被改为 /unified-orders。"""
    async with test_session() as s:
        s.add(BottomNavConfig(name="订单", icon_key="order", path="/orders", sort_order=3, is_visible=True, is_fixed=False))
        s.add(BottomNavConfig(name="我的订单", icon_key="order", path="/orders", sort_order=4, is_visible=True, is_fixed=False))
        s.add(BottomNavConfig(name="Orders", icon_key="order", path="/orders", sort_order=5, is_visible=True, is_fixed=False))
        await s.commit()

    await migrate_bottom_nav_order_path()

    async with test_session() as s:
        from sqlalchemy import select
        rows = (await s.execute(select(BottomNavConfig))).scalars().all()
        for r in rows:
            assert r.path == "/unified-orders", f"{r.name} 未被迁移: path={r.path}"


@pytest.mark.asyncio
async def test_migrate_order_path_does_not_touch_other_names():
    """name 不属于订单命名白名单的 /orders 记录不应被修改。"""
    async with test_session() as s:
        s.add(BottomNavConfig(name="自定义菜单", icon_key="order", path="/orders", sort_order=3, is_visible=True, is_fixed=False))
        await s.commit()

    await migrate_bottom_nav_order_path()

    async with test_session() as s:
        from sqlalchemy import select
        row = (await s.execute(select(BottomNavConfig).where(BottomNavConfig.name == "自定义菜单"))).scalar_one()
        assert row.path == "/orders"


@pytest.mark.asyncio
async def test_migrate_order_path_idempotent():
    """多次执行迁移，不应产生副作用（幂等）。"""
    async with test_session() as s:
        s.add(BottomNavConfig(name="订单", icon_key="order", path="/orders", sort_order=3, is_visible=True, is_fixed=False))
        await s.commit()

    await migrate_bottom_nav_order_path()
    await migrate_bottom_nav_order_path()
    await migrate_bottom_nav_order_path()

    async with test_session() as s:
        from sqlalchemy import select
        row = (await s.execute(select(BottomNavConfig).where(BottomNavConfig.name == "订单"))).scalar_one()
        assert row.path == "/unified-orders"


@pytest.mark.asyncio
async def test_migrate_order_path_no_matching_rows():
    """无匹配记录时应直接跳过，不报错。"""
    await migrate_bottom_nav_order_path()
