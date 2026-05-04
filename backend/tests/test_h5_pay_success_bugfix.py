"""[H5 支付 Bug 修复方案 v1.0 · 支付成功页与安全增强] 后端回归测试

针对 PRD `H5 支付 BUG 修复方案文档`新增的标准版支付成功页和安全防伪要求，补充验证：

1. test_pay_success_requires_auth_and_returns_404_for_other_user
   订单详情接口必须经过鉴权，且无法读取他人订单（防伪造）
2. test_paid_order_detail_exposes_required_fields_for_pay_success_page
   /pay/success 页所需字段（order_no / paid_amount / payment_method / created_at /
   items[].fulfillment_type / items[].appointment_mode）必须从订单详情接口透出
3. test_zero_order_full_processing_chain_after_confirm_free
   0 元订单经 confirm-free 后必须完成"完整支付成功后处理"：
     a) 优惠券核销（user_coupon.status -> used）
     b) 库存扣减（在订单创建时即完成）
     c) 订单状态推进
4. test_confirm_free_unauthenticated_returns_401
   未认证调 confirm-free 必须 401，符合 PRD §B1 安全要求
5. test_pay_unauthenticated_returns_401
   未认证调 /pay 必须 401（防止前端绕过鉴权）
6. test_create_order_unauthenticated_returns_401
   未认证调 /api/orders/unified 必须 401
7. test_paid_order_payment_method_text_present_for_paid_h5_order
   付费 H5 订单 payment_method_text 必须被构造（沙盒 confirm 后），
   支撑支付成功页的"支付方式"展示
8. test_zero_order_can_load_order_detail_after_confirm_free
   0 元订单 confirm-free 后用 GET /{id} 仍能正常加载（支付成功页拉取场景）

测试方法：复用 test_h5_pay_link_bugfix.py 的工具函数风格，直接 DB
fixture 操作 PaymentChannel / Coupon / UserCoupon。
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
# 工具函数（与 test_h5_pay_link_bugfix.py 同款，避免跨文件 import 风险）
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
    fulfillment_type: str = "in_store",
    appointment_mode: str = "none",
    initial_stock: int = 100,
) -> int:
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": fulfillment_type,
        "original_price": sale_price + 1,
        "sale_price": sale_price,
        "stock": initial_stock,
        "status": "active",
        "images": ["https://example.com/test.jpg"],
        "appointment_mode": appointment_mode,
        "purchase_appointment_mode": "purchase_with_appointment",
    }
    # 预约模式（date / time_slot）下，advance_days 必须 > 0；time_slot 还需要 time_slots 数组
    if appointment_mode in ("date", "time_slot"):
        payload["advance_days"] = 7
    if appointment_mode == "time_slot":
        payload["time_slots"] = [
            {"start": "09:00", "end": "10:00", "capacity": 5},
            {"start": "10:00", "end": "11:00", "capacity": 5},
        ]
    resp = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _ensure_payment_channel(
    db_session, *, channel_code: str, platform: str, provider: str,
    is_enabled: bool, is_complete: bool = True, display_name: str = None,
) -> PaymentChannel:
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


async def _create_full_reduction_coupon_and_grant(
    db_session, *, user_id: int, discount_value: float,
) -> tuple[int, int]:
    coupon = Coupon(
        name="测试满减券",
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
    return coupon.id, uc.id


async def _get_user_id(db_session, phone: str) -> int:
    rs = await db_session.execute(select(User).where(User.phone == phone))
    return rs.scalar_one().id


async def _register_second_user(client: AsyncClient, phone: str = "13900000088") -> str:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "user123", "nickname": "他人B",
    })
    resp = await client.post("/api/auth/login", json={
        "phone": phone, "password": "user123",
    })
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 用例 1：订单详情接口必须鉴权 + 不能读他人订单（PRD §B5 防伪造加固）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_success_requires_auth_and_returns_404_for_other_user(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    pid = await _create_product(
        client, admin_headers, name="他人订单详情测试", cat_name="PaySuc-Forbidden", sale_price=10.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order_id = create_resp.json()["id"]

    # ① 未认证：必须 401
    no_auth_resp = await client.get(f"/api/orders/unified/{order_id}")
    assert no_auth_resp.status_code == 401, no_auth_resp.text

    # ② 他人认证：必须 404（按现有项目实现：他人订单视为不存在）
    token_b = await _register_second_user(client, phone="13900000088")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    other_resp = await client.get(f"/api/orders/unified/{order_id}", headers=headers_b)
    assert other_resp.status_code == 404, other_resp.text


# ---------------------------------------------------------------------------
# 用例 2：付费订单详情透出 /pay/success 所需字段（PRD §3.1）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paid_order_detail_exposes_required_fields_for_pay_success_page(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """支付成功页需要：order_no / paid_amount / payment_method /
    created_at / items[].fulfillment_type / items[].appointment_mode。"""
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="预约商品", cat_name="PaySuc-Detail",
        sale_price=66.0, fulfillment_type="in_store", appointment_mode="time_slot",
    )
    # 预约类商品创单必须携带 appointment_time/appointment_data（明天 09:00）
    appt_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{
                "product_id": pid,
                "quantity": 1,
                "appointment_time": f"{appt_date}T09:00:00",
                "appointment_data": {"date": appt_date, "time_slot": "09:00-10:00"},
            }],
            "payment_method": "alipay",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order_id = create_resp.json()["id"]

    # 先 /pay 推进到已支付（含 payment_channel_code 落库）
    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "alipay", "channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 200, pay_resp.text

    detail_resp = await client.get(
        f"/api/orders/unified/{order_id}", headers=auth_headers,
    )
    assert detail_resp.status_code == 200, detail_resp.text
    body = detail_resp.json()

    # 关键字段必须透出（支撑成功页 UI 渲染）
    assert body.get("order_no"), "order_no 必须透出"
    assert "paid_amount" in body, "paid_amount 必须透出"
    assert body.get("payment_method") == "alipay", f"payment_method 应为 alipay；实际={body.get('payment_method')}"
    assert body.get("created_at"), "created_at 必须透出"
    assert isinstance(body.get("items"), list) and len(body["items"]) > 0
    item0 = body["items"][0]
    assert item0.get("fulfillment_type") == "in_store"
    assert item0.get("appointment_mode") in ("time_slot", "TIME_SLOT"), (
        f"appointment_mode 必须透出（用于 F5 智能跳转）；实际={item0}"
    )
    assert item0.get("product_name"), "product_name 必须透出"


# ---------------------------------------------------------------------------
# 用例 3：0 元订单 confirm-free 后必须完成完整链路（券核销 + 库存扣减 + 状态推进）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_order_full_processing_chain_after_confirm_free(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """PRD §B3：0 元订单完成流程必须复用付费订单"支付成功后处理"链路。"""
    pid = await _create_product(
        client, admin_headers, name="0元完整链路", cat_name="PaySuc-Free",
        sale_price=88.0, initial_stock=10,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id, uc_id = await _create_full_reduction_coupon_and_grant(
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

    # confirm-free
    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={}, headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text
    body = free_resp.json()
    assert body["status"] != "pending_payment", "状态必须从待支付推进"

    # ① 优惠券核销
    await db_session.refresh(await _get_user_coupon(db_session, uc_id))
    uc = await _get_user_coupon(db_session, uc_id)
    uc_status = uc.status.value if hasattr(uc.status, "value") else uc.status
    assert uc_status == "used", f"0元订单优惠券必须被核销；实际={uc_status}"

    # ② 库存扣减（创建订单时已完成；这里再次确认）
    detail_resp = await client.get(f"/api/products/{pid}")
    if detail_resp.status_code == 200:
        prod = detail_resp.json()
        # stock 应已从 10 减 1 → 9
        assert int(prod.get("stock", 0)) == 9, f"库存必须扣减 1；实际={prod.get('stock')}"


async def _get_user_coupon(db_session, uc_id: int) -> UserCoupon:
    rs = await db_session.execute(select(UserCoupon).where(UserCoupon.id == uc_id))
    return rs.scalar_one()


# ---------------------------------------------------------------------------
# 用例 4：未认证调 confirm-free 返回 401（PRD §B1 防伪造）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_free_unauthenticated_returns_401(
    client: AsyncClient, admin_headers, auth_headers,
):
    pid = await _create_product(
        client, admin_headers, name="未认证测试", cat_name="PaySuc-Auth", sale_price=10.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    order_id = create_resp.json()["id"]

    # 不带 token
    resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free", json={},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 用例 5：未认证调 /pay 返回 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_unauthenticated_returns_401(
    client: AsyncClient, admin_headers, auth_headers,
):
    pid = await _create_product(
        client, admin_headers, name="未认证 /pay 测试", cat_name="PaySuc-PayAuth",
        sale_price=10.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "alipay", "channel_code": "alipay_h5"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 用例 6：未认证调 POST /api/orders/unified 创单 返回 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_order_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": 1, "quantity": 1}], "payment_method": "alipay"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 用例 7：付费 H5 订单 payment_method_text 必须被构造（沙盒确认后）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paid_order_payment_method_text_present_for_paid_h5_order(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    await _ensure_payment_channel(
        db_session, channel_code="alipay_h5", platform="h5", provider="alipay",
        is_enabled=True, display_name="支付宝",
    )
    pid = await _create_product(
        client, admin_headers, name="付费H5订单 PMT", cat_name="PaySuc-PMText",
        sale_price=12.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    order_id = create_resp.json()["id"]

    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "alipay", "channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 200

    detail_resp = await client.get(
        f"/api/orders/unified/{order_id}", headers=auth_headers,
    )
    body = detail_resp.json()
    pmt = body.get("payment_method_text")
    assert pmt and "支付宝" in pmt and "H5" in pmt, (
        f"payment_method_text 必须包含通道显示名+端名（如「支付宝（H5）」）；实际={pmt}"
    )


# ---------------------------------------------------------------------------
# 用例 8：0 元订单 confirm-free 后能正常加载详情（成功页拉取场景）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_order_can_load_order_detail_after_confirm_free(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    pid = await _create_product(
        client, admin_headers, name="0元成功页加载", cat_name="PaySuc-FreeLoad",
        sale_price=20.0,
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

    # confirm-free
    await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={}, headers=auth_headers,
    )

    # 模拟支付成功页拉详情
    detail_resp = await client.get(
        f"/api/orders/unified/{order_id}", headers=auth_headers,
    )
    assert detail_resp.status_code == 200, detail_resp.text
    body = detail_resp.json()
    assert float(body["paid_amount"]) == 0.0
    assert body["paid_at"] is not None
    assert body["status"] != "pending_payment"
    # coupon_discount 应大于 0（说明用券抵扣）
    assert float(body.get("coupon_discount", 0)) > 0
