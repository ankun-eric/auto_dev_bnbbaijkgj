"""[H5 支付链路修复 v1.0] 后端回归测试

覆盖修复方案的关键场景，至少 8 个 pytest-asyncio 用例：

1. test_available_methods_h5_returns_only_enabled
2. test_create_order_with_full_amount_returns_pay_url_after_pay
3. test_pay_with_disabled_channel_returns_4001
4. test_confirm_free_happy_path
5. test_confirm_free_rejects_paid_amount_gt_zero
6. test_confirm_free_rejects_other_users_order
7. test_confirm_free_rejects_already_paid_order
8. test_confirm_free_allows_null_channel_when_all_disabled

测试方法：直接通过 db_session 调整 PaymentChannel 启用状态、UserCoupon 抵扣金额，
绕过后台接口对 superuser 的强校验。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    Coupon,
    CouponType,
    PaymentChannel,
    User,
    UserCoupon,
    UserCouponStatus,
)


# ---------------------------------------------------------------------------
# 工具函数
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


async def _ensure_payment_channel(
    db_session, *, channel_code: str, platform: str, provider: str,
    is_enabled: bool, is_complete: bool = True, display_name: str = None,
) -> PaymentChannel:
    """直接 DB 写入 PaymentChannel，避开后台超管校验。"""
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
    return ch


async def _disable_all_payment_channels(db_session) -> None:
    rs = await db_session.execute(select(PaymentChannel))
    for ch in rs.scalars().all():
        ch.is_enabled = False
    await db_session.commit()


async def _create_full_reduction_coupon_and_grant(
    db_session, *, user_id: int, discount_value: float,
) -> tuple[int, int]:
    """直接在 DB 创建满减券 + UserCoupon，便于在订单创建时把 paid_amount 抵到 0。"""
    coupon = Coupon(
        name="测试满减券",
        type=CouponType.full_reduction,
        condition_amount=0,  # 无门槛
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
    return coupon.id, uc.id


async def _get_user_id(db_session, phone: str) -> int:
    rs = await db_session.execute(select(User).where(User.phone == phone))
    u = rs.scalar_one()
    return u.id


async def _register_second_user(client: AsyncClient, phone: str = "13900000099") -> str:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "user123", "nickname": "用户B",
    })
    resp = await client.post("/api/auth/login", json={
        "phone": phone, "password": "user123",
    })
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 用例 1：H5 端 available-methods 仅返回启用通道
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_available_methods_h5_returns_only_enabled(
    client: AsyncClient, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    await _ensure_payment_channel(
        db_session, channel_code="wechat_h5", platform="h5", provider="wechat",
        is_enabled=False, display_name="微信支付",
    )

    resp = await client.get("/api/pay/available-methods", params={"platform": "h5"})
    assert resp.status_code == 200, resp.text
    items = resp.json()
    codes = [it["channel_code"] for it in items]
    assert "alipay_h5" in codes, f"启用的 alipay_h5 必须返回；实际={items}"
    assert "wechat_h5" not in codes, f"未启用的 wechat_h5 不应返回；实际={items}"


# ---------------------------------------------------------------------------
# 用例 2：付费订单 /pay 返回 pay_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_order_with_full_amount_returns_pay_url_after_pay(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="付费H5商品", cat_name="H5-Pay-Cat", sale_price=99.0,
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
    body = pay_resp.json()
    assert body.get("pay_url"), f"alipay_h5 通道必须返回非空 pay_url；body={body}"
    assert "alipay_h5" in body["pay_url"]
    assert body.get("channel_code") == "alipay_h5"


# ---------------------------------------------------------------------------
# 用例 3：通道未启用 → /pay 返回 4001
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_with_disabled_channel_returns_4001(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=False, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="通道关测试", cat_name="H5-Disabled", sale_price=10.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order_id = create_resp.json()["id"]

    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "alipay", "channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 400, pay_resp.text
    detail = pay_resp.json().get("detail")
    assert isinstance(detail, dict), f"detail 应为 dict；实际={detail}"
    assert detail.get("code") == 4001, f"必须返回 code=4001；实际={detail}"


# ---------------------------------------------------------------------------
# 用例 4：confirm-free happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_happy_path(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="0元商品", cat_name="H5-Free", sale_price=50.0,
    )

    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id, _ = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,  # 必然把 paid_amount 抵到 0
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
    assert float(order["paid_amount"]) == 0.0, f"前置：满减券必须把 paid_amount 抵为 0；实际={order}"
    order_id = order["id"]

    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={"channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text
    body = free_resp.json()
    assert body["paid_at"] is not None
    # status 必须已推进（从 pending_payment 走开），到店商品 → pending_use
    assert body["status"] != "pending_payment", f"confirm-free 后状态必须推进；body={body}"


# ---------------------------------------------------------------------------
# 用例 5：confirm-free 拒绝 paid_amount > 0（防绕过）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_rejects_paid_amount_gt_zero(
    client: AsyncClient, admin_headers, auth_headers,
):
    pid = await _create_product(
        client, admin_headers, name="付费商品-防绕过", cat_name="H5-Bypass", sale_price=88.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()
    assert float(order["paid_amount"]) > 0
    order_id = order["id"]

    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={},
        headers=auth_headers,
    )
    assert free_resp.status_code == 400, free_resp.text
    detail = free_resp.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "not_free_order", (
        f"非 0 元订单必须返回 code=not_free_order；实际={detail}"
    )


# ---------------------------------------------------------------------------
# 用例 6：confirm-free 拒绝其他用户的订单
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_rejects_other_users_order(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    pid = await _create_product(
        client, admin_headers, name="他人订单测试", cat_name="H5-Forbidden", sale_price=20.0,
    )
    user_a_id = await _get_user_id(db_session, "13900000001")
    coupon_id, _ = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_a_id, discount_value=999,
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

    token_b = await _register_second_user(client, phone="13900000099")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={},
        headers=headers_b,
    )
    assert free_resp.status_code == 403, free_resp.text
    detail = free_resp.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "forbidden", f"实际={detail}"


# ---------------------------------------------------------------------------
# 用例 7：confirm-free 拒绝已支付订单
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_rejects_already_paid_order(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    pid = await _create_product(
        client, admin_headers, name="已支付订单测试", cat_name="H5-Paid", sale_price=30.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id, _ = await _create_full_reduction_coupon_and_grant(
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
    order_id = create_resp.json()["id"]

    # 先合法走一次 confirm-free 让订单推进
    first = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={}, headers=auth_headers,
    )
    assert first.status_code == 200, first.text

    # 再调一次：状态已不是 pending_payment → 400 invalid_status
    second = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={}, headers=auth_headers,
    )
    assert second.status_code == 400, second.text
    detail = second.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "invalid_status", f"实际={detail}"


# ---------------------------------------------------------------------------
# 用例 8：通道全关时 0 元订单允许 channel_code=null
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_allows_null_channel_when_all_disabled(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _disable_all_payment_channels(db_session)

    pid = await _create_product(
        client, admin_headers, name="全关0元商品", cat_name="H5-AllOff", sale_price=15.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id, _ = await _create_full_reduction_coupon_and_grant(
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

    # 不传 channel_code
    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={},
        headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text
    body = free_resp.json()
    assert body["paid_at"] is not None
    assert body.get("payment_channel_code") in (None, ""), (
        f"通道全关时 0 元订单 payment_channel_code 应为 null/空；实际={body}"
    )
