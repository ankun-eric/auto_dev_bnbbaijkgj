"""[2026-05-05 H5 优惠券抵扣 0 元下单 Bug 修复 v1.2 · R4] 后端回归测试

新发现的根因 R4：
    生产数据库 user_coupons 表存在脏数据，同一 (user_id, coupon_id, status=unused)
    可能出现多条记录。原 `unified_orders.py:551 / 995` 使用 `scalar_one_or_none()`
    会抛 sqlalchemy.exc.MultipleResultsFound → uncaught → 500 Internal Server Error。

修复（v1.2 · R4）：
    将 `.scalar_one_or_none()` 改为 `.order_by(expire_at, id).scalars().first()`，
    自动选取「最早过期 / 最小 id」的那张参与下单与核销，对脏数据完全容错。
    同步修复 `coupons.py:182` 的领券重复检查。

本文件覆盖：
- 用例 R4-A（核心）：同一用户对同一券存在 3 条 unused 记录，使用全额券下 0 元单不再 500
- 用例 R4-B（核销正确性）：下单成功后只核销 1 张（最早过期那张），其余 unused 保持
- 用例 R4-C（领取容错）：重复领取查询不再 500，正确返回 409 Conflict
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    Coupon,
    CouponType,
    UnifiedOrder,
    User,
    UserCoupon,
    UserCouponStatus,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_product(
    client: AsyncClient,
    admin_headers,
    *,
    name: str,
    cat_name: str,
    sale_price: float = 100.0,
) -> int:
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": "in_store",
        "original_price": sale_price + 1,
        "sale_price": sale_price,
        "stock": 100,
        "status": "active",
        "images": ["https://example.com/test.jpg"],
        "appointment_mode": "none",
        "purchase_appointment_mode": "purchase_with_appointment",
    }
    resp = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_full_reduction_coupon(db_session, *, name: str) -> int:
    coupon = Coupon(
        name=name,
        type=CouponType.full_reduction,
        condition_amount=0,
        discount_value=999,
        discount_rate=1.0,
        scope="all",
        scope_ids=None,
        validity_days=30,
        status="active",
        total_count=100,
        claimed_count=10,
    )
    db_session.add(coupon)
    await db_session.flush()
    return coupon.id


async def _grant_user_coupons(
    db_session, *, user_id: int, coupon_id: int, count: int, base_offset_days: int = 30,
) -> list[int]:
    """模拟脏数据：给同一用户同一券派发 count 张 unused 记录，
    expire_at 各不相同（确保 ORDER BY 行为可观测）。
    """
    ids: list[int] = []
    now = datetime.utcnow()
    for i in range(count):
        uc = UserCoupon(
            user_id=user_id,
            coupon_id=coupon_id,
            status=UserCouponStatus.unused,
            expire_at=now + timedelta(days=base_offset_days + i * 5),
        )
        db_session.add(uc)
        await db_session.flush()
        ids.append(uc.id)
    await db_session.commit()
    return ids


async def _get_user_id(db_session, phone: str) -> int:
    rs = await db_session.execute(select(User).where(User.phone == phone))
    return rs.scalar_one().id


# ---------------------------------------------------------------------------
# 用例 R4-A（核心）：同一 (user, coupon) 多条 unused 不再触发 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_r4_a_zero_order_with_duplicate_user_coupons_no_500(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[R4 核心：原始 Bug 复现]
    场景：用户对同一张全额券持有 3 条 unused 记录（脏数据），
    使用该券下 0 元单。
    期望：
      1) 不再抛 MultipleResultsFound，POST /api/orders/unified 返回 200
      2) DB 落库 payment_method='coupon_deduction'，paid_amount=0
    """
    pid = await _create_product(
        client, admin_headers, name="R4-A零元单商品", cat_name="R4-A-cat", sale_price=66.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon(db_session, name="R4-A满减券")
    grant_ids = await _grant_user_coupons(
        db_session, user_id=user_id, coupon_id=coupon_id, count=3,
    )
    assert len(grant_ids) == 3

    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "coupon_deduction",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, (
        f"脏数据场景下不应 500；status={resp.status_code} body={resp.text}"
    )
    order = resp.json()
    assert float(order["paid_amount"]) == 0.0

    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order["id"])
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm == "coupon_deduction"


# ---------------------------------------------------------------------------
# 用例 R4-B（核销正确性）：脏数据场景下只核销 1 张，其余 unused 保持
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_r4_b_only_one_user_coupon_consumed_when_duplicates_exist(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[R4 核销正确性]
    场景：用户对同一张全额券持有 3 条 unused 记录，下单成功。
    期望：
      - 仅 1 张被标记为 used（最早过期 / 最小 id 那张）
      - 其余 2 张保持 unused，不能被错误连带核销
    """
    pid = await _create_product(
        client, admin_headers, name="R4-B商品", cat_name="R4-B-cat", sale_price=88.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon(db_session, name="R4-B满减券")
    grant_ids = await _grant_user_coupons(
        db_session, user_id=user_id, coupon_id=coupon_id, count=3,
    )

    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "coupon_deduction",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text

    # 重新查询 UC 状态分布
    await db_session.commit()
    rs = await db_session.execute(
        select(UserCoupon)
        .where(
            UserCoupon.user_id == user_id,
            UserCoupon.coupon_id == coupon_id,
        )
        .order_by(UserCoupon.id.asc())
    )
    rows = rs.scalars().all()
    used = [r for r in rows if (r.status.value if hasattr(r.status, "value") else r.status) == "used"]
    unused = [r for r in rows if (r.status.value if hasattr(r.status, "value") else r.status) == "unused"]
    assert len(used) == 1, f"应仅 1 张被核销；实际 used={len(used)} unused={len(unused)}"
    assert len(unused) == 2, f"应保留 2 张 unused；实际 unused={len(unused)}"
    # 被核销的那张应是「最早过期 / 最小 id」
    assert used[0].id == grant_ids[0], (
        f"应核销最早过期那张（id={grant_ids[0]}）；实际核销 id={used[0].id}"
    )


# ---------------------------------------------------------------------------
# 用例 R4-C（领取容错）：重复领取查询不再 500，仍返回 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_r4_c_claim_existing_coupon_returns_409_not_500_when_duplicates(
    client: AsyncClient, auth_headers, db_session,
):
    """[R4 领取容错]
    场景：用户已持有同一张券的 2 条 unused 记录（脏数据），再次调用 /api/coupons/claim。
    期望：
      - 不抛 MultipleResultsFound
      - 返回 409 Conflict（"您已领取过该优惠券"）
    """
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon(db_session, name="R4-C领取容错券")
    await _grant_user_coupons(
        db_session, user_id=user_id, coupon_id=coupon_id, count=2,
    )

    resp = await client.post(
        "/api/coupons/claim",
        json={"coupon_id": coupon_id},
        headers=auth_headers,
    )
    # 关键：不能是 500
    assert resp.status_code != 500, f"重复领取查询不应 500；body={resp.text}"
    # 期望 409 Conflict
    assert resp.status_code == 409, (
        f"已领取过应返回 409；实际 {resp.status_code} body={resp.text}"
    )
