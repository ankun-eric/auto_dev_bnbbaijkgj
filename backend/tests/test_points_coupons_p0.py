"""Bug #3 / Bug #4 P0 修复单元测试

覆盖：
- Bug #3（优惠券合计口径）：已用 / 已过期 / 前端 Tab 与顶部"合计(N)"数据一致
- Bug #4（积分可用积分口径）：累计获得 − 已消耗 − 已过期 − 已冻结
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.models import (
    Coupon,
    CouponStatus,
    CouponType,
    PointsRecord,
    PointsType,
    User,
    UserCoupon,
    UserCouponStatus,
)
from tests.conftest import test_session


# ───────── 通用辅助 ─────────


async def _get_user_id(phone: str) -> int:
    async with test_session() as session:
        rs = await session.execute(select(User).where(User.phone == phone))
        user = rs.scalar_one()
        return user.id


@pytest_asyncio.fixture
async def coupon_fixture():
    """建一张基础优惠券，供 UserCoupon 外键使用。"""
    async with test_session() as session:
        c = Coupon(
            name="测试券",
            type=CouponType.full_reduction,
            condition_amount=100,
            discount_value=10,
            discount_rate=1.0,
            total_count=0,
            validity_days=30,
            status=CouponStatus.active,
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        return c.id


# ───────── Bug #3：优惠券合计口径 ─────────


@pytest.mark.asyncio
async def test_coupons_summary_excludes_used_and_expired(
    client: AsyncClient, auth_headers, coupon_fixture: int
):
    """合计 = 未使用且未过期。已用 / 已过期不计入。"""
    user_id = await _get_user_id("13900000001")
    now = datetime.utcnow()

    async with test_session() as session:
        # 1 张：可用（未使用 + 未来过期）
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.unused,
            expire_at=now + timedelta(days=10),
        ))
        # 1 张：可用（未使用 + 过期时间为 NULL，视为永久有效）
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.unused,
            expire_at=None,
        ))
        # 1 张：已使用（不计入）
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.used,
            expire_at=now + timedelta(days=10),
            used_at=now - timedelta(days=1),
        ))
        # 1 张：已过期（status=expired，不计入）
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.expired,
            expire_at=now - timedelta(days=1),
        ))
        # 1 张：未使用但已过期（按口径：仍视为已过期，不计入可用）
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.unused,
            expire_at=now - timedelta(hours=1),
        ))
        await session.commit()

    resp = await client.get("/api/coupons/summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["available"] == 2, data
    assert data["available_count"] == 2
    assert data["used"] == 1
    # 已过期包括：status=expired（1 张）+ unused 且 expire_at<=now（1 张）= 2 张
    assert data["expired"] == 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_mine_coupons_available_count_matches_tab(
    client: AsyncClient, auth_headers, coupon_fixture: int
):
    """GET /api/coupons/mine 响应里的 available_count 必须等于 /summary.available，
    保证前端"合计(N)"与"可用(N)" Tab 数据一致。"""
    user_id = await _get_user_id("13900000001")
    now = datetime.utcnow()

    async with test_session() as session:
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.unused,
            expire_at=now + timedelta(days=5),
        ))
        session.add(UserCoupon(
            user_id=user_id, coupon_id=coupon_fixture,
            status=UserCouponStatus.used,
            expire_at=now + timedelta(days=5),
        ))
        await session.commit()

    mine_resp = await client.get("/api/coupons/mine", headers=auth_headers, params={"tab": "all"})
    assert mine_resp.status_code == 200, mine_resp.text
    mine = mine_resp.json()

    summary_resp = await client.get("/api/coupons/summary", headers=auth_headers)
    summary = summary_resp.json()

    assert mine["available_count"] == summary["available"] == 1


# ───────── Bug #4：积分可用积分口径 ─────────


@pytest.mark.asyncio
async def test_points_available_earned_minus_consumed(
    client: AsyncClient, auth_headers,
):
    """可用积分 = 累计获得 − 已消耗（当前枚举无 expire/frozen）"""
    user_id = await _get_user_id("13900000001")

    async with test_session() as session:
        session.add(PointsRecord(user_id=user_id, points=100, type=PointsType.signin, description="签到"))
        session.add(PointsRecord(user_id=user_id, points=50, type=PointsType.task, description="任务"))
        session.add(PointsRecord(user_id=user_id, points=-30, type=PointsType.redeem, description="兑换"))
        session.add(PointsRecord(user_id=user_id, points=-20, type=PointsType.deduct, description="扣除"))
        await session.commit()

    resp = await client.get("/api/points/summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # 100 + 50 − 30 − 20 = 100
    assert data["breakdown"]["earned"] == 150
    assert data["breakdown"]["consumed"] == 50
    assert data["breakdown"]["expired"] == 0
    assert data["breakdown"]["frozen"] == 0
    assert data["available_points"] == 100
    assert data["total_points"] == 100


@pytest.mark.asyncio
async def test_points_balance_uses_computed_not_cached(
    client: AsyncClient, auth_headers,
):
    """user.points 缓存字段不一致时，接口必须以流水计算结果为准，且不修改缓存。"""
    user_id = await _get_user_id("13900000001")

    async with test_session() as session:
        user = await session.get(User, user_id)
        user.points = 9999  # 故意塞一个错误缓存值
        session.add(PointsRecord(user_id=user_id, points=10, type=PointsType.signin))
        session.add(PointsRecord(user_id=user_id, points=-3, type=PointsType.redeem))
        await session.commit()

    resp = await client.get("/api/points/balance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == 7
    assert data["available_points"] == 7

    # 验证接口未修改 user.points 缓存字段（仅读取，不回写）
    async with test_session() as session:
        user = await session.get(User, user_id)
        assert user.points == 9999


@pytest.mark.asyncio
async def test_points_available_never_negative(
    client: AsyncClient, auth_headers,
):
    """消耗 > 获得 时，可用积分最小为 0，不得出现负数。"""
    user_id = await _get_user_id("13900000001")

    async with test_session() as session:
        session.add(PointsRecord(user_id=user_id, points=5, type=PointsType.signin))
        session.add(PointsRecord(user_id=user_id, points=-50, type=PointsType.redeem))
        await session.commit()

    resp = await client.get("/api/points/summary", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["available_points"] == 0
