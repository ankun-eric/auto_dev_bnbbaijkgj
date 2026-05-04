"""[支付宝 H5 正式支付链路接入 v1.0] 后端回归测试

覆盖 PRD §5.1 要求的 9 个用例：

T-01 创建 alipay_h5 订单（金额 > 0），mock 支付宝返回正常 → pay_url 前缀为
     https://openapi.alipay.com/gateway.do?
T-02 同上，订单金额=0 → 不调用支付宝，走原"零元订单"分支
T-03 异步通知：合法验签 + TRADE_SUCCESS → 订单状态推进到"已支付"，返回 success
T-04 异步通知：同一订单重复 POST 5 次 → 状态只翻一次，5 次都返回 success（幂等）
T-05 异步通知：total_amount 被篡改 → 拒绝处理，返回 fail，订单状态不变
T-06 异步通知：签名错误 → 拒绝处理，返回 fail
T-07 测试按钮：参数齐全且与支付宝匹配（mock query 返 ACQ.TRADE_NOT_EXIST）→ 返回成功
T-08 测试按钮：私钥与 AppID 不匹配（mock query 返 ISV.INVALID_SIGNATURE）→ 失败
T-09 测试按钮：网络出网被禁（mock raise ConnectionError）→ 失败 + "网络不通"文案

测试方法：
- 使用 monkeypatch 替换 alipay_service 中的关键函数（_build_client_from_config、
  query_trade、verify_async_notify、create_wap_pay_url），避免依赖真实
  python-alipay-sdk 与真实网络。
- 直接通过 db_session 调整 PaymentChannel 的 is_complete + config_json，
  绕过加密 / 完整性校验。
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
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.utils.crypto import encrypt_value


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


async def _ensure_alipay_h5_channel(
    db_session,
    *,
    is_enabled: bool = True,
    is_complete: bool = True,
    with_config: bool = True,
) -> PaymentChannel:
    """直接 DB 写入 alipay_h5 通道。

    with_config=True 时写入"看起来齐全"的加密配置（公钥模式），
    便于 alipay_service 进入 _build_client_from_config 时不会因解密自检失败。
    （后续测试用 monkeypatch 替换 _build_client_from_config 屏蔽真实 SDK。）
    """
    rs = await db_session.execute(
        select(PaymentChannel).where(PaymentChannel.channel_code == "alipay_h5")
    )
    ch = rs.scalar_one_or_none()
    if ch is None:
        ch = PaymentChannel(
            channel_code="alipay_h5",
            channel_name="支付宝H5支付",
            display_name="支付宝",
            platform="h5",
            provider="alipay",
            is_enabled=is_enabled,
            is_complete=is_complete,
            sort_order=10,
            config_json={},
        )
        db_session.add(ch)
    else:
        ch.is_enabled = is_enabled
        ch.is_complete = is_complete

    if with_config:
        ch.config_json = {
            "app_id": "2021000123456789",
            "access_mode": "public_key",
            "app_private_key": encrypt_value("FAKE_APP_PRIVATE_KEY_FOR_TEST"),
            "alipay_public_key": encrypt_value("FAKE_ALIPAY_PUBLIC_KEY_FOR_TEST"),
        }
    else:
        ch.config_json = {}
    await db_session.commit()
    await db_session.refresh(ch)
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


# ---------------------------------------------------------------------------
# Fakes：替换 alipay_service 的关键函数
# ---------------------------------------------------------------------------


class _FakeAlipayClient:
    """伪客户端，被注入到 alipay_service 中替代真实 SDK 实例。"""


def _patch_real_pay_url(monkeypatch, *, gateway_url: str | None = None):
    """让 _build_alipay_h5_pay_url 返回真实生产网关 URL。"""
    from app.api import unified_orders as uo_mod

    async def _fake_get_client(db, channel_code="alipay_h5"):
        rs = await db.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == channel_code)
        )
        ch = rs.scalar_one_or_none()
        if ch is None or not ch.is_complete:
            raise ValueError("配置不完整")
        return _FakeAlipayClient(), ch

    def _fake_create_url(client, **kw):
        return (
            gateway_url
            or f"https://openapi.alipay.com/gateway.do?out_trade_no={kw['out_trade_no']}&app_id=2021000123456789"
        )

    # 替换 alipay_service 模块中的两个函数
    monkeypatch.setattr(
        "app.services.alipay_service.get_alipay_client_for_channel",
        _fake_get_client,
    )
    monkeypatch.setattr(
        "app.services.alipay_service.create_wap_pay_url",
        _fake_create_url,
    )


def _patch_verify_notify(monkeypatch, *, ok: bool):
    """让 verify_async_notify 返回固定结果。"""
    monkeypatch.setattr(
        "app.api.alipay_notify.verify_async_notify",
        lambda client, form_dict: ok,
    )

    async def _fake_get_client(db, channel_code="alipay_h5"):
        rs = await db.execute(
            select(PaymentChannel).where(PaymentChannel.channel_code == channel_code)
        )
        ch = rs.scalar_one_or_none()
        if ch is None:
            raise ValueError("通道未找到")
        return _FakeAlipayClient(), ch

    monkeypatch.setattr(
        "app.api.alipay_notify.get_alipay_client_for_channel",
        _fake_get_client,
    )


# ---------------------------------------------------------------------------
# 用例 T-01：alipay_h5 + paid_amount > 0 → 真实网关 URL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t01_create_alipay_h5_returns_real_gateway_url(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
):
    await _ensure_alipay_h5_channel(db_session, is_enabled=True, is_complete=True)
    _patch_real_pay_url(monkeypatch)

    pid = await _create_product(
        client, admin_headers, name="付费H5商品", cat_name="T01-Cat", sale_price=99.0,
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
    assert pay_resp.status_code == 200, pay_resp.text
    body = pay_resp.json()
    assert body.get("pay_url", "").startswith(
        "https://openapi.alipay.com/gateway.do?"
    ), f"pay_url 必须为真实生产网关；实际={body.get('pay_url')}"

    # 真实链路下，订单状态应仍为 pending_payment，等异步通知再翻
    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = rs.scalar_one()
    status_val = order.status.value if hasattr(order.status, "value") else order.status
    assert status_val == "pending_payment", (
        f"真实支付宝链路 /pay 后状态必须仍为 pending_payment；实际={status_val}"
    )
    assert order.paid_at is None, "真实链路下 paid_at 不应在 /pay 阶段写入"


# ---------------------------------------------------------------------------
# 用例 T-02：金额为 0 → 不调用支付宝，走 confirm-free
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t02_zero_amount_does_not_call_alipay(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
):
    await _ensure_alipay_h5_channel(db_session, is_enabled=True, is_complete=True)

    # 让 _build_alipay_h5_pay_url 一旦被调用就抛异常（明确证明未调用）
    called = {"count": 0}

    def _fake_create_url(client, **kw):
        called["count"] += 1
        raise AssertionError("零元订单不应调用 create_wap_pay_url")

    monkeypatch.setattr("app.services.alipay_service.create_wap_pay_url", _fake_create_url)

    pid = await _create_product(
        client, admin_headers, name="0元商品", cat_name="T02-Cat", sale_price=50.0,
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

    # 走 0 元免支付分支
    free_resp = await client.post(
        f"/api/orders/unified/{order_id}/confirm-free",
        json={"channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert free_resp.status_code == 200, free_resp.text
    assert called["count"] == 0, "零元订单链路必须未调用支付宝"


# ---------------------------------------------------------------------------
# 用例 T-03：异步通知合法 + TRADE_SUCCESS → 状态推进
# ---------------------------------------------------------------------------


async def _create_pending_alipay_order(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
    *, sale_price: float = 99.0,
) -> tuple[int, str]:
    """创建一笔 alipay_h5 待支付订单，返回 (order_id, order_no)。"""
    await _ensure_alipay_h5_channel(db_session, is_enabled=True, is_complete=True)
    _patch_real_pay_url(monkeypatch)
    pid = await _create_product(
        client, admin_headers, name="异步通知测试", cat_name=f"NT-{sale_price}",
        sale_price=sale_price,
    )
    create_resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "alipay"},
        headers=auth_headers,
    )
    order = create_resp.json()
    order_id = order["id"]
    order_no = order["order_no"]
    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "alipay", "channel_code": "alipay_h5"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 200
    return order_id, order_no


@pytest.mark.asyncio
async def test_t03_async_notify_success_advances_status(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
):
    order_id, order_no = await _create_pending_alipay_order(
        client, admin_headers, auth_headers, db_session, monkeypatch, sale_price=99.0,
    )
    _patch_verify_notify(monkeypatch, ok=True)

    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = rs.scalar_one()
    paid_amount = float(order.paid_amount or 0)

    notify_data = {
        "app_id": "2021000123456789",
        "out_trade_no": order_no,
        "trade_no": "2026050422001234567890",
        "total_amount": f"{paid_amount:.2f}",
        "trade_status": "TRADE_SUCCESS",
        "buyer_logon_id": "13900000099@163.com",
        "sign": "fake_sign_value",
        "sign_type": "RSA2",
    }
    resp = await client.post("/api/payment/alipay/notify", data=notify_data)
    assert resp.status_code == 200, resp.text
    assert resp.text == "success", f"必须返回纯文本 success；实际={resp.text!r}"

    # 状态应已推进
    db_session.expire_all()
    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = rs.scalar_one()
    status_val = order.status.value if hasattr(order.status, "value") else order.status
    assert status_val != "pending_payment", f"异步通知后状态必须推进；实际={status_val}"
    assert order.paid_at is not None, "异步通知后 paid_at 必须写入"


# ---------------------------------------------------------------------------
# 用例 T-04：异步通知幂等 — 重复 POST 5 次状态只翻一次
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t04_async_notify_idempotent(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
):
    order_id, order_no = await _create_pending_alipay_order(
        client, admin_headers, auth_headers, db_session, monkeypatch, sale_price=88.0,
    )
    _patch_verify_notify(monkeypatch, ok=True)

    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    paid_amount = float(rs.scalar_one().paid_amount or 0)

    notify_data = {
        "app_id": "2021000123456789",
        "out_trade_no": order_no,
        "trade_no": "2026050422001999",
        "total_amount": f"{paid_amount:.2f}",
        "trade_status": "TRADE_SUCCESS",
        "sign": "fake_sign",
        "sign_type": "RSA2",
    }
    paid_at_values = []
    for _ in range(5):
        resp = await client.post("/api/payment/alipay/notify", data=notify_data)
        assert resp.status_code == 200
        assert resp.text == "success"
        db_session.expire_all()
        rs2 = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
        paid_at_values.append(rs2.scalar_one().paid_at)

    # 5 次的 paid_at 必须完全一致（说明只翻了第一次）
    assert all(v == paid_at_values[0] for v in paid_at_values), (
        f"幂等失败：paid_at 在重复通知中被多次写入；序列={paid_at_values}"
    )


# ---------------------------------------------------------------------------
# 用例 T-05：金额被篡改 → fail 且不变更
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t05_async_notify_amount_tampered_rejected(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
):
    order_id, order_no = await _create_pending_alipay_order(
        client, admin_headers, auth_headers, db_session, monkeypatch, sale_price=77.0,
    )
    _patch_verify_notify(monkeypatch, ok=True)

    notify_data = {
        "app_id": "2021000123456789",
        "out_trade_no": order_no,
        "trade_no": "2026050422001ATTACK",
        "total_amount": "0.01",  # 故意被篡改
        "trade_status": "TRADE_SUCCESS",
        "sign": "fake",
        "sign_type": "RSA2",
    }
    resp = await client.post("/api/payment/alipay/notify", data=notify_data)
    assert resp.status_code == 200
    assert resp.text != "success", f"金额被篡改必须返回非 success；实际={resp.text!r}"

    # 状态应保持 pending_payment
    db_session.expire_all()
    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = rs.scalar_one()
    status_val = order.status.value if hasattr(order.status, "value") else order.status
    assert status_val == "pending_payment", (
        f"金额被篡改后状态必须保持 pending_payment；实际={status_val}"
    )


# ---------------------------------------------------------------------------
# 用例 T-06：签名错误 → fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t06_async_notify_invalid_sign_rejected(
    client: AsyncClient, admin_headers, auth_headers, db_session, monkeypatch,
):
    order_id, order_no = await _create_pending_alipay_order(
        client, admin_headers, auth_headers, db_session, monkeypatch, sale_price=66.0,
    )
    _patch_verify_notify(monkeypatch, ok=False)  # 模拟验签失败

    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    paid_amount = float(rs.scalar_one().paid_amount or 0)
    notify_data = {
        "app_id": "2021000123456789",
        "out_trade_no": order_no,
        "trade_no": "2026050422006SIGNFAIL",
        "total_amount": f"{paid_amount:.2f}",
        "trade_status": "TRADE_SUCCESS",
        "sign": "INVALID_SIGN",
        "sign_type": "RSA2",
    }
    resp = await client.post("/api/payment/alipay/notify", data=notify_data)
    assert resp.status_code == 200
    assert resp.text != "success", (
        f"签名失败必须返回非 success；实际={resp.text!r}"
    )


# ---------------------------------------------------------------------------
# 用例 T-07/T-08/T-09：测试按钮的三种结果
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t07_test_button_success_when_trade_not_exist(
    client: AsyncClient, admin_headers, db_session, monkeypatch,
):
    await _ensure_alipay_h5_channel(db_session, is_enabled=False, is_complete=True)

    monkeypatch.setattr(
        "app.services.alipay_service._build_client_from_config",
        lambda code, cfg: _FakeAlipayClient(),
    )
    monkeypatch.setattr(
        "app.services.alipay_service.query_trade",
        lambda client, no: {"code": "40004", "msg": "Business Failed",
                             "sub_code": "ACQ.TRADE_NOT_EXIST",
                             "sub_msg": "交易不存在"},
    )
    resp = await client.post(
        "/api/admin/payment-channels/alipay_h5/test", headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "测试通过" in body["message"]


@pytest.mark.asyncio
async def test_t08_test_button_invalid_signature(
    client: AsyncClient, admin_headers, db_session, monkeypatch,
):
    await _ensure_alipay_h5_channel(db_session, is_enabled=False, is_complete=True)

    monkeypatch.setattr(
        "app.services.alipay_service._build_client_from_config",
        lambda code, cfg: _FakeAlipayClient(),
    )
    monkeypatch.setattr(
        "app.services.alipay_service.query_trade",
        lambda client, no: {"code": "40002", "msg": "Invalid Arguments",
                             "sub_code": "ISV.INVALID_SIGNATURE",
                             "sub_msg": "签名错误"},
    )
    resp = await client.post(
        "/api/admin/payment-channels/alipay_h5/test", headers=admin_headers,
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json().get("detail", "")
    assert "签名" in str(detail), f"必须包含'签名'关键词；实际={detail}"


@pytest.mark.asyncio
async def test_t09_test_button_network_unreachable(
    client: AsyncClient, admin_headers, db_session, monkeypatch,
):
    await _ensure_alipay_h5_channel(db_session, is_enabled=False, is_complete=True)

    monkeypatch.setattr(
        "app.services.alipay_service._build_client_from_config",
        lambda code, cfg: _FakeAlipayClient(),
    )

    def _raise_timeout(client, no):
        raise ConnectionError("Connection timed out")

    monkeypatch.setattr(
        "app.services.alipay_service.query_trade",
        _raise_timeout,
    )
    resp = await client.post(
        "/api/admin/payment-channels/alipay_h5/test", headers=admin_headers,
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json().get("detail", "")
    assert "网络不通" in str(detail), f"必须包含'网络不通'关键词；实际={detail}"
