"""Tests for "我的" stats aggregation, coupons exclude_expired,
and admin product categories reorder."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from sqlalchemy import select

from app.models.models import (
    Coupon,
    CouponStatus,
    Favorite,
    ProductCategory,
    User,
    UserCoupon,
    UserCouponStatus,
)
from tests.conftest import test_session


async def _get_user_id_by_phone(phone: str) -> int:
    async with test_session() as db:
        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()
        return user.id if user else 0


async def _seed_coupon(name="测试券", days_valid=30):
    async with test_session() as db:
        now = datetime.utcnow()
        c = Coupon(
            name=name,
            type="full_reduction",
            condition_amount=10,
            discount_value=5,
            discount_rate=1.0,
            valid_start=now - timedelta(days=1),
            valid_end=now + timedelta(days=days_valid),
            total_count=100,
            claimed_count=0,
            status=CouponStatus.active,
        )
        db.add(c)
        await db.commit()
        return c.id


async def _give_user_coupon(user_id: int, coupon_id: int, status="unused"):
    async with test_session() as db:
        uc = UserCoupon(user_id=user_id, coupon_id=coupon_id, status=status)
        db.add(uc)
        await db.commit()
        return uc.id


async def _add_favorite(user_id: int, content_type="product", content_id=1):
    async with test_session() as db:
        fav = Favorite(user_id=user_id, content_type=content_type, content_id=content_id)
        db.add(fav)
        await db.commit()


async def _seed_root_category(name: str, sort_order: int = 0) -> int:
    async with test_session() as db:
        cat = ProductCategory(name=name, status="active", sort_order=sort_order, level=1, parent_id=None)
        db.add(cat)
        await db.commit()
        return cat.id


@pytest.mark.asyncio
async def test_my_stats_unauthorized(client: AsyncClient):
    """T7: 未登录访问 /api/users/me/stats 返回 401"""
    resp = await client.get("/api/users/me/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_my_stats_aggregates_coupons_and_favorites(
    client: AsyncClient, auth_headers
):
    """T1+T2: 未使用未过期券 + 收藏不分类型计数"""
    user_id = await _get_user_id_by_phone("13900000001")
    assert user_id > 0

    # 5 张未使用券：3 张未过期 + 2 张过期
    valid_ids = [await _seed_coupon(f"valid-{i}", days_valid=30) for i in range(3)]
    expired_ids = [await _seed_coupon(f"expired-{i}", days_valid=-1) for i in range(2)]
    for cid in valid_ids + expired_ids:
        await _give_user_coupon(user_id, cid, status="unused")

    # 收藏：8 个商品 + 2 篇文章
    for pid in range(1, 9):
        await _add_favorite(user_id, "product", pid)
    for aid in range(1, 3):
        await _add_favorite(user_id, "article", aid)

    resp = await client.get("/api/users/me/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["coupon_count"] == 3
    assert data["favorite_count"] == 10
    assert data["points"] >= 0


@pytest.mark.asyncio
async def test_coupons_mine_exclude_expired(
    client: AsyncClient, auth_headers
):
    """exclude_expired=true 应过滤掉已过期券"""
    user_id = await _get_user_id_by_phone("13900000001")
    assert user_id > 0

    valid_ids = [await _seed_coupon(f"v-{i}", days_valid=30) for i in range(2)]
    expired_id = await _seed_coupon("e-1", days_valid=-1)
    for cid in valid_ids + [expired_id]:
        await _give_user_coupon(user_id, cid, status="unused")

    # 默认行为：不过滤
    resp_default = await client.get("/api/coupons/mine?tab=unused", headers=auth_headers)
    assert resp_default.status_code == 200
    assert resp_default.json()["total"] >= 3

    # exclude_expired=true：只返回未过期
    resp_filtered = await client.get(
        "/api/coupons/mine?tab=unused&exclude_expired=true", headers=auth_headers
    )
    assert resp_filtered.status_code == 200
    assert resp_filtered.json()["total"] == 2


@pytest.mark.asyncio
async def test_admin_categories_reorder(client: AsyncClient, admin_headers):
    """T3+T4: 拖拽排序顺序生效"""
    cat_a = await _seed_root_category("A 分类", sort_order=0)
    cat_b = await _seed_root_category("B 分类", sort_order=1)
    cat_c = await _seed_root_category("C 分类", sort_order=2)

    resp = await client.post(
        "/api/admin/products/categories/reorder",
        json={"parent_id": None, "ordered_ids": [cat_c, cat_a, cat_b]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "排序" in resp.json()["message"]

    list_resp = await client.get("/api/products/categories")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    ids_in_order = [c["id"] for c in items if c["id"] in {cat_a, cat_b, cat_c}]
    assert ids_in_order == [cat_c, cat_a, cat_b]
