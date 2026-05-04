"""[2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0] 后端回归测试

原始 Bug 现象：
    H5 端用户使用全额抵扣券下单时，前端组装请求 payment_method='alipay'，
    后端 POST /api/orders/unified 接口返回 500，订单创建失败。
    confirm-free 分支根本走不到。

本次修复（B1）：
    后端 `create_unified_order` 在 paid_amount==0 时，
    server-side 强制把 payment_method 改写为 'coupon_deduction'，
    作为最后一道防线，独立于前端是否升级。

本文件覆盖修复方案 §五 的关键用例：
- 用例 G1（核心）：原始 Bug 复现 — 优惠券抵扣后实付 0 元创建订单不再失败
- 用例 G3（边界）：积分抵扣到 0 元下单
- 用例 G4（回归）：非 0 元正常下单不受影响
- 用例 G6（防绕过）：前端绕过传 alipay，server-side 兜底改写为 coupon_deduction
- B3 单测   ：响应 payment_method_text 中文映射统一为「优惠券全额抵扣」
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


async def _create_full_reduction_coupon_and_grant(
    db_session, *, user_id: int, discount_value: float,
) -> int:
    coupon = Coupon(
        name="0元单v1.0测试满减券",
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
# 用例 G1（核心）：原始 Bug 复现 — 实付 0 元创建订单不再 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_g1_zero_order_create_no_500_with_coupon_deduction_payment_method(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[原始 Bug 复现用例]
    场景：H5 端使用全额抵扣券，前端按修复后的 A1 方案传 payment_method='coupon_deduction'。
    期望：
      1) POST /api/orders/unified 返回 200（不再 500）
      2) DB 中 payment_method = 'coupon_deduction'
      3) paid_amount = 0
    """
    pid = await _create_product(
        client, admin_headers, name="G1零元单商品", cat_name="ZeroV10-G1", sale_price=66.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,
    )

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            # 关键：前端 A1 修复后会传 coupon_deduction
            "payment_method": "coupon_deduction",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    # 修复前这里会 500，修复后应 200
    assert create_resp.status_code == 200, (
        f"实付 0 元创建订单不应 500；status={create_resp.status_code}, body={create_resp.text}"
    )
    order = create_resp.json()
    assert float(order["paid_amount"]) == 0.0
    order_id = order["id"]

    # DB 验证
    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order_id)
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm == "coupon_deduction", (
        f"前端传 coupon_deduction，DB 落库必须为 coupon_deduction；实际={pm!r}"
    )


# ---------------------------------------------------------------------------
# 用例 G3（边界）：积分抵扣到 0 元
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_g3_zero_order_via_points_deduction_records_coupon_deduction(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[边界场景]
    场景：用户用积分把订单实付抵到 0 元（不用券）。
    期望（用户决策口径 A）：
      统一记 payment_method='coupon_deduction'，B1 server-side 兜底生效。
    """
    pid = await _create_product(
        client, admin_headers, name="G3积分抵零商品", cat_name="ZeroV10-G3", sale_price=2.0,
    )
    # 给用户充足积分（200 积分 = 2 元 = 商品总价）
    user_id = await _get_user_id(db_session, "13900000001")
    rs = await db_session.execute(select(User).where(User.id == user_id))
    user = rs.scalar_one()
    user.points = 1000
    await db_session.commit()

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            # 注意：这里前端传 alipay（即未升级或未走券路径），
            # 但 200 积分把 2 元抵扣到 0 元，B1 server-side 兜底必须改写为 coupon_deduction
            "payment_method": "alipay",
            "points_deduction": 200,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()
    assert float(order["paid_amount"]) == 0.0
    order_id = order["id"]

    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order_id)
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm == "coupon_deduction", (
        f"积分抵到 0 元应统一记 coupon_deduction；实际={pm!r}"
    )


# ---------------------------------------------------------------------------
# 用例 G4（回归）：非 0 元正常下单不受影响
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_g4_non_zero_order_keeps_original_payment_method(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[回归保护]
    场景：选商品不用券，正常 alipay/wechat 支付。
    期望：payment_method 保持原值（alipay/wechat），不被误改写。
    """
    pid = await _create_product(
        client, admin_headers, name="G4正常下单商品", cat_name="ZeroV10-G4", sale_price=15.0,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()
    order_id = order["id"]
    assert float(order["paid_amount"]) > 0

    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order_id)
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm == "alipay", (
        f"非 0 元订单 payment_method 不应被改写；实际={pm!r}"
    )


# ---------------------------------------------------------------------------
# 用例 G6（防绕过）：用 Postman 构造 alipay 但券抵到 0 元，
# server-side 兜底必须把 payment_method 改为 coupon_deduction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_g6_server_side_override_when_old_client_sends_alipay_with_full_coupon(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[防绕过 / B1 验证]
    场景：老客户端（A1 未升级）仍传 payment_method='alipay'，
         但券抵到 0 元 → server-side 必须兜底改写为 coupon_deduction。
    期望：
      1) 创建订单返回 200（不再 500）
      2) DB 落库 payment_method = 'coupon_deduction'
    """
    pid = await _create_product(
        client, admin_headers, name="G6绕过验证商品", cat_name="ZeroV10-G6", sale_price=100.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,
    )

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay",  # 关键：老客户端仍传 alipay
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, (
        f"server-side 必须兜底，老客户端传 alipay+全额券抵 0 元仍应 200；body={create_resp.text}"
    )
    order = create_resp.json()
    assert float(order["paid_amount"]) == 0.0

    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order["id"])
    )
    db_order = rs.scalar_one()
    pm = db_order.payment_method
    if hasattr(pm, "value"):
        pm = pm.value
    assert pm == "coupon_deduction", (
        f"server-side 兜底必须改写 0 元单的 payment_method；实际={pm!r}"
    )


# ---------------------------------------------------------------------------
# 用例 B3：响应 payment_method_text 中文映射
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_b3_payment_method_text_for_coupon_deduction_zero_order(
    client: AsyncClient, admin_headers, auth_headers, db_session,
):
    """[B3 后端文案统一]
    场景：0 元单创建后查询订单详情。
    期望：响应 `payment_method_text` 字段为 '优惠券全额抵扣'，
         前端无需各自硬编码映射。
    """
    pid = await _create_product(
        client, admin_headers, name="B3文案商品", cat_name="ZeroV10-B3", sale_price=66.0,
    )
    user_id = await _get_user_id(db_session, "13900000001")
    coupon_id = await _create_full_reduction_coupon_and_grant(
        db_session, user_id=user_id, discount_value=999,
    )

    create_resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "coupon_deduction",
            "coupon_id": coupon_id,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    order_id = create_resp.json()["id"]

    detail_resp = await client.get(
        f"/api/orders/unified/{order_id}",
        headers=auth_headers,
    )
    assert detail_resp.status_code == 200, detail_resp.text
    body = detail_resp.json()
    assert body.get("payment_method") == "coupon_deduction", body
    # 后端 _build_payment_method_text 已为 coupon_deduction 增加中文兜底
    assert body.get("payment_method_text") == "优惠券全额抵扣", (
        f"payment_method_text 应为 '优惠券全额抵扣'；实际={body.get('payment_method_text')!r}"
    )


# ---------------------------------------------------------------------------
# 用例 SCHEMA：UnifiedPaymentMethod 枚举包含 coupon_deduction 与 balance
# ---------------------------------------------------------------------------

def test_schema_payment_method_enum_includes_balance_and_coupon_deduction():
    """[B2 枚举占位]
    UnifiedPaymentMethod 必须同时包含 coupon_deduction 与 balance 两个值，
    与 admin payMethodMap、各端中文映射全端口径对齐。
    """
    values = {m.value for m in UnifiedPaymentMethod}
    assert "coupon_deduction" in values
    assert "balance" in values
    assert "wechat" in values
    assert "alipay" in values


# ---------------------------------------------------------------------------
# 用例 SCHEMA-2：ALLOWED_PAYMENT_METHODS 与 PAYMENT_METHOD_TEXT_MAP 一致
# ---------------------------------------------------------------------------

def test_schema_allowed_payment_methods_and_text_map_consistency():
    """[B3 文案口径一致性]
    Schema 白名单与中文映射必须协同：
      - 白名单允许 coupon_deduction / balance 通过 schema 校验
      - 中文映射对应的中文文案与 admin/前端约定一致
    """
    from app.schemas.unified_orders import (
        ALLOWED_PAYMENT_METHODS,
        PAYMENT_METHOD_TEXT_MAP,
    )

    assert "coupon_deduction" in ALLOWED_PAYMENT_METHODS
    assert "balance" in ALLOWED_PAYMENT_METHODS
    assert PAYMENT_METHOD_TEXT_MAP["coupon_deduction"] == "优惠券全额抵扣"
    assert PAYMENT_METHOD_TEXT_MAP["balance"] == "余额支付"
    assert PAYMENT_METHOD_TEXT_MAP["wechat"] == "微信支付"
    assert PAYMENT_METHOD_TEXT_MAP["alipay"] == "支付宝"


# ---------------------------------------------------------------------------
# 用例 SCHEMA-3：normalize_payment_method 仍正常归一化通道编码
# ---------------------------------------------------------------------------

def test_schema_normalize_payment_method_still_works():
    """[B2 兼容性]
    扩展白名单后，老客户端的通道编码归一化仍应正常工作：
      - alipay_h5  → alipay
      - wechat_app → wechat
      - coupon_deduction → coupon_deduction（白名单内精确匹配）
      - balance → balance
    """
    from app.schemas.unified_orders import normalize_payment_method

    assert normalize_payment_method("alipay_h5") == "alipay"
    assert normalize_payment_method("wechat_miniprogram") == "wechat"
    assert normalize_payment_method("alipay_app") == "alipay"
    assert normalize_payment_method("coupon_deduction") == "coupon_deduction"
    assert normalize_payment_method("balance") == "balance"
    assert normalize_payment_method("wechat") == "wechat"
    assert normalize_payment_method("alipay") == "alipay"
    assert normalize_payment_method(None) is None
    assert normalize_payment_method("") is None
    # 非合法值仍返回 None（由调用方决定如何处理）
    assert normalize_payment_method("foo_bar") is None
