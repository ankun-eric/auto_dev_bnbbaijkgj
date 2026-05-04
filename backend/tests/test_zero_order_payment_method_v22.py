"""[零元单 Bug 修复 v2.2] 后端回归测试

覆盖修复方案 §五 的关键用例（精简版，与 test_h5_pay_link_bugfix.py 互补）：

1. test_confirm_free_writes_payment_method_coupon_deduction
   —— 0 元单走 confirm-free 后，DB 中 payment_method = 'coupon_deduction'
2. test_confirm_free_payment_method_in_response
   —— 接口响应中 payment_method 字段值为 'coupon_deduction'
3. test_paid_order_keeps_original_payment_method
   —— 走真实 /pay 链路的有金额订单 payment_method 不会被错误改为 coupon_deduction
4. test_confirm_free_payment_method_query_finance
   —— 财务对账 SQL `WHERE payment_method='coupon_deduction'` 能拿到 0 元单
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.models import (
    Coupon,
    CouponType,
    PaymentChannel,
    UnifiedOrder,
    UnifiedPaymentMethod,
    User,
    UserCoupon,
    UserCouponStatus,
)


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
    fulfillment_type: str = "in_store",
) -> int:
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": fulfillment_type,
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


async def _ensure_payment_channel(
    db_session, *, channel_code: str, platform: str, provider: str,
    is_enabled: bool, is_complete: bool = True, display_name: str = None,
):
    rs = await db_session.execute(
        select(PaymentChannel).where(PaymentChannel.channel_code == channel_code)
    )
    ch = rs.scalar_one_or_none()
    if ch is None:
        ch = PaymentChannel(
            channel_code=channel_code,
            channel_name=channel_code,
            display_name=display_name or channel_code,
            platform=platform,
            provider=provider,
            is_enabled=is_enabled,
            is_complete=is_complete,
            sort_order=10,
        )
        db_session.add(ch)
    else:
        ch.is_enabled = is_enabled
        ch.is_complete = is_complete
        ch.platform = platform
        ch.provider = provider
        if display_name:
            ch.display_name = display_name
    await db_session.commit()


async def _create_full_reduction_coupon_and_grant(
    db_session, *, user_id: int, discount_value: float,
) -> int:
    coupon = Coupon(
        name="零元测试满减券",
        type=CouponType.full_reduction,
        condition_amount=0,
        discount_value=discount_value,
        discount_rate=1.0,
        scope="all",
        scope_ids=None,
        validity_days=30,
        status="active",
        total_count=100,
        claimed_count=1,
    )
    db_session.add(coupon)
    await db_session.flush()
    uc = UserCoupon(
        user_id=user_id,
        coupon_id=coupon.id,
        status=UserCouponStatus.unused,
        expire_at=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(uc)
    await db_session.commit()
    return coupon.id


async def _get_user_id(db_session, phone: str) -> int:
    rs = await db_session.execute(select(User).where(User.phone == phone))
    u = rs.scalar_one()
    return u.id


# ---------------------------------------------------------------------------
# 用例 1：confirm-free 后 DB payment_method = 'coupon_deduction'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_writes_payment_method_coupon_deduction(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="零元单v22商品A", cat_name="ZeroV22-Cat-A", sale_price=66.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,
    )

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()
    assert float(order["paid_amount"]) == 0.0
    order_id = order["id"]

    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={"channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text

    # 直读 DB 验证 payment_method
    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order_id)
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm == "coupon_deduction", (
        f"0 元单 confirm-free 后 payment_method 必须为 coupon_deduction；实际={pm!r}"
    )
    assert db_order.paid_at is not None


# ---------------------------------------------------------------------------
# 用例 2：confirm-free 接口响应中 payment_method 字段
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_payment_method_in_response(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    pid = await _create_product(
        client, admin_headers, name="零元单v22商品B", cat_name="ZeroV22-Cat-B", sale_price=88.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,
    )

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order_id = create_resp.json()["id"]

    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={},
        headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text
    body = free_resp.json()
    pm = body.get("payment_method")
    assert pm == "coupon_deduction", (
        f"confirm-free 响应中 payment_method 必须为 coupon_deduction；实际 body={body}"
    )


# ---------------------------------------------------------------------------
# 用例 3：付费订单走 /pay 不会误标 coupon_deduction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paid_order_keeps_original_payment_method(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="付费订单v22", cat_name="ZeroV22-Cat-C", sale_price=15.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()
    order_id = order["id"]
    assert float(order["paid_amount"]) > 0

    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "alipay", "channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 200, pay_resp.text

    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order_id)
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm != "coupon_deduction", (
        f"有金额订单 payment_method 不应被改为 coupon_deduction；实际={pm!r}"
    )


# ---------------------------------------------------------------------------
# 用例 4：财务对账 SQL `WHERE payment_method='coupon_deduction'` 命中 0 元单
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_payment_method_query_finance(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    pid = await _create_product(
        client, admin_headers, name="对账查询v22", cat_name="ZeroV22-Cat-D", sale_price=10.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,
    )

    # 取本次插入前的基线计数，避免与其它测试用例创建的订单互相干扰
    baseline_rs = await db_session.execute(
        select(func.count(UnifiedOrder.id)).where(
            UnifiedOrder.payment_method == UnifiedPaymentMethod.coupon_deduction
        )
    )
    baseline = int(baseline_rs.scalar() or 0)

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order_id = create_resp.json()["id"]
    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={},
        headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text

    # 再次统计，应正好多 1 单
    after_rs = await db_session.execute(
        select(func.count(UnifiedOrder.id)).where(
            UnifiedOrder.payment_method == UnifiedPaymentMethod.coupon_deduction
        )
    )
    after = int(after_rs.scalar() or 0)
    assert after == baseline + 1, (
        f"对账查询命中数应增加 1；baseline={baseline} after={after}"
    )
