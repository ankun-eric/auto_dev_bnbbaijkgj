"""[2026-05-04 支付通道枚举不一致 Bug 修复 v1.0] 回归测试

覆盖如下场景：
  1. H5/小程序/Flutter 三端创建订单时若误传 channel_code（wechat_h5 / wechat_miniprogram /
     alipay_app），后端应自动归一化为 provider 级（wechat / alipay）写库；
  2. 直接传合法 provider 级值（wechat / alipay），落库不变；
  3. 传无法识别的非法值（如 foo_bar），应返回 422（schema 拒绝）；
  4. 不传 payment_method（None），允许，落库为 None。

这些用例对应 Bug 文档第 4.6 节"回归测试用例补强"。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.unified_orders import (
    ALLOWED_PAYMENT_METHODS,
    UnifiedOrderCreate,
    normalize_payment_method,
)


# ---------------------------------------------------------------------------
# 工具：复用现有的商品创建辅助函数
# ---------------------------------------------------------------------------

async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_simple_product(
    client: AsyncClient, admin_headers, *, name: str, cat_name: str,
) -> int:
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": "in_store",
        "original_price": 99,
        "sale_price": 88,
        "stock": 100,
        "status": "active",
        "images": ["https://example.com/test.jpg"],
        "appointment_mode": "none",
        "purchase_appointment_mode": "purchase_with_appointment",
    }
    resp = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# 单元测试：normalize_payment_method 工具函数
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        # 已经是 provider 级
        ("wechat", "wechat"),
        ("alipay", "alipay"),
        ("WECHAT", "wechat"),  # 大小写兼容
        # H5 通道编码
        ("wechat_h5", "wechat"),
        ("alipay_h5", "alipay"),
        # 小程序通道
        ("wechat_miniprogram", "wechat"),
        # APP 通道
        ("wechat_app", "wechat"),
        ("alipay_app", "alipay"),
        # 边界
        (None, None),
        ("", None),
        ("  ", None),
        # 非法 → None（由调用方决定如何处理）
        ("foo_bar", None),
        ("paypal", None),
        ("unionpay_h5", None),
    ],
)
def test_normalize_payment_method(raw, expected):
    assert normalize_payment_method(raw) == expected


def test_allowed_payment_methods_constant():
    """ALLOWED_PAYMENT_METHODS 必须仅包含 wechat / alipay 两个 provider。"""
    assert ALLOWED_PAYMENT_METHODS == {"wechat", "alipay"}


# ---------------------------------------------------------------------------
# Schema 校验：UnifiedOrderCreate.payment_method
# ---------------------------------------------------------------------------

def test_schema_accepts_provider_level_values():
    o = UnifiedOrderCreate(
        items=[{"product_id": 1, "quantity": 1}],
        payment_method="wechat",
    )
    assert o.payment_method == "wechat"

    o2 = UnifiedOrderCreate(
        items=[{"product_id": 1, "quantity": 1}],
        payment_method="alipay",
    )
    assert o2.payment_method == "alipay"


def test_schema_normalizes_channel_code_to_provider():
    """三端历史脏值必须被自动归一化为 provider。"""
    cases = {
        "wechat_h5": "wechat",
        "alipay_h5": "alipay",
        "wechat_miniprogram": "wechat",
        "wechat_app": "wechat",
        "alipay_app": "alipay",
    }
    for raw, expected in cases.items():
        o = UnifiedOrderCreate(
            items=[{"product_id": 1, "quantity": 1}],
            payment_method=raw,
        )
        assert o.payment_method == expected, (
            f"channel_code={raw} 应自动归一化为 {expected}，实际={o.payment_method}"
        )


def test_schema_rejects_unknown_payment_method():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UnifiedOrderCreate(
            items=[{"product_id": 1, "quantity": 1}],
            payment_method="paypal",  # 不在白名单 + 无法归一化
        )

    with pytest.raises(ValidationError):
        UnifiedOrderCreate(
            items=[{"product_id": 1, "quantity": 1}],
            payment_method="foo_bar",
        )


def test_schema_allows_null_payment_method():
    """payment_method=None 合法，等价于不传，落库为 None。"""
    o = UnifiedOrderCreate(items=[{"product_id": 1, "quantity": 1}], payment_method=None)
    assert o.payment_method is None

    o2 = UnifiedOrderCreate(items=[{"product_id": 1, "quantity": 1}])
    assert o2.payment_method is None


# ---------------------------------------------------------------------------
# 集成测试：真实创建订单接口
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_order_with_h5_channel_code_normalized_to_wechat(
    client: AsyncClient, admin_headers, auth_headers,
):
    """模拟历史 H5 端 Bug：误传 wechat_h5 → 后端必须落库为 wechat。"""
    pid = await _create_simple_product(
        client, admin_headers, name="H5支付方式测试-1", cat_name="PM-Norm-1",
    )
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat_h5",  # 老前端误传 channel_code
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    order = resp.json()
    assert order["payment_method"] == "wechat", (
        f"wechat_h5 必须自动归一化为 wechat 后入库；实际={order['payment_method']}"
    )


@pytest.mark.asyncio
async def test_create_order_with_alipay_h5_normalized_to_alipay(
    client: AsyncClient, admin_headers, auth_headers,
):
    pid = await _create_simple_product(
        client, admin_headers, name="H5支付方式测试-2", cat_name="PM-Norm-2",
    )
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay_h5",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_method"] == "alipay"


@pytest.mark.asyncio
async def test_create_order_with_miniprogram_channel_normalized(
    client: AsyncClient, admin_headers, auth_headers,
):
    pid = await _create_simple_product(
        client, admin_headers, name="小程序支付方式测试", cat_name="PM-Norm-3",
    )
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat_miniprogram",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_method"] == "wechat"


@pytest.mark.asyncio
async def test_create_order_with_app_channel_normalized(
    client: AsyncClient, admin_headers, auth_headers,
):
    pid = await _create_simple_product(
        client, admin_headers, name="APP支付方式测试", cat_name="PM-Norm-4",
    )
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "alipay_app",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_method"] == "alipay"


@pytest.mark.asyncio
async def test_create_order_with_provider_level_values_unchanged(
    client: AsyncClient, admin_headers, auth_headers,
):
    """传入合法 provider 级值时入库值不变。"""
    pid = await _create_simple_product(
        client, admin_headers, name="provider直传测试", cat_name="PM-Norm-5",
    )
    for pm in ("wechat", "alipay"):
        resp = await client.post(
            "/api/orders/unified",
            json={
                "items": [{"product_id": pid, "quantity": 1}],
                "payment_method": pm,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["payment_method"] == pm


@pytest.mark.asyncio
async def test_create_order_with_unknown_payment_method_rejected(
    client: AsyncClient, admin_headers, auth_headers,
):
    """不可识别的支付方式：返回 422（schema 拒绝）。"""
    pid = await _create_simple_product(
        client, admin_headers, name="非法支付方式测试", cat_name="PM-Norm-6",
    )
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "paypal",
        },
        headers=auth_headers,
    )
    # FastAPI/pydantic v2 对 ValueError 默认返回 422
    assert resp.status_code in (400, 422), resp.text


@pytest.mark.asyncio
async def test_create_order_distinct_payment_method_only_provider_level(
    client: AsyncClient, admin_headers, auth_headers,
):
    """端到端验收：连续创建多笔订单（无论传 channel_code 还是 provider），
    最终入库的 payment_method 集合应该只包含 provider 级别值。"""
    pid = await _create_simple_product(
        client, admin_headers, name="distinct测试", cat_name="PM-Norm-7",
    )
    raw_inputs = ["wechat_h5", "alipay_h5", "wechat_miniprogram", "alipay_app", "wechat", "alipay"]
    persisted = set()
    for pm in raw_inputs:
        resp = await client.post(
            "/api/orders/unified",
            json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": pm},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"input={pm}, resp={resp.text}"
        persisted.add(resp.json()["payment_method"])
    assert persisted <= {"wechat", "alipay"}, (
        f"入库的 payment_method 集合必须只包含 wechat / alipay；实际={persisted}"
    )
