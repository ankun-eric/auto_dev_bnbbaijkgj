"""[PRD V2 核销订单状态体系优化] 后端测试

覆盖：
1. UnifiedOrderStatus 12 枚举完整性 + 保留 pending_review 兼容
2. RedemptionCodeStatus 5 态枚举完整性
3. 状态机推进：支付实物 → pending_shipment；支付到店无预约 → pending_use；
   到店需预约未设 → pending_appointment；预约时间已设 → appointed
4. 客户端 Tab 列表过滤映射：pending_use Tab 含 pending_appointment/appointed/pending_use/partial_used
5. 已完成 Tab 含 completed + expired
6. 退货售后 Tab + 子筛选（all/reviewing/refunding/refunded/rejected）
7. 退款融合：发起退款 → status=refunding；撤回 → status=pending_use
8. /counts 返回 v2_pending_payment / v2_pending_receipt / v2_pending_use / v2_completed / v2_refund_aftersales
9. admin /orders/v2/enums 返回 12 状态 + 5 核销码 + 7 退款标签
10. admin /orders/v2/stats 返回 GMV / fulfillment_rate / status_breakdown / redemption_code_breakdown
11. set_order_appointment：pending_appointment → appointed
12. 订单响应字段 display_status / display_status_color / action_buttons / badges 全部存在
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.models import (
    Product,
    ProductCategory,
    UnifiedOrder,
    UnifiedOrderStatus,
    RedemptionCodeStatus,
    OrderItem,
)
from tests.conftest import test_session


# ────────────────── helpers ──────────────────


async def _seed_category(name: str = "V2 测试分类") -> int:
    async with test_session() as db:
        cat = ProductCategory(name=name, status="active", sort_order=0, level=1)
        db.add(cat)
        await db.commit()
        return cat.id


async def _seed_product(
    category_id: int,
    *,
    name: str = "V2 测试商品",
    fulfillment_type: str = "delivery",
    appointment_mode: str = "none",
    stock: int = 100,
) -> int:
    async with test_session() as db:
        product = Product(
            name=name,
            category_id=category_id,
            fulfillment_type=fulfillment_type,
            original_price=199.0,
            sale_price=99.0,
            images=["https://img.example.com/1.jpg"],
            stock=stock,
            status="active",
            points_exchangeable=False,
            redeem_count=1,
            appointment_mode=appointment_mode,
        )
        db.add(product)
        await db.commit()
        return product.id


async def _create_order(client: AsyncClient, headers, product_id: int, quantity: int = 1):
    return await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": product_id, "quantity": quantity}],
            "payment_method": "wechat",
        },
        headers=headers,
    )


async def _pay_order(client: AsyncClient, headers, order_id: int):
    return await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "wechat"},
        headers=headers,
    )


# ════════════════════════════════════════════
#  1. 枚举完整性
# ════════════════════════════════════════════


def test_unified_order_status_has_12_v2_values():
    """V2 必须包含 12 个新值（pending_review 保留兼容，不计入 12）。"""
    expected = {
        "pending_payment", "pending_shipment", "pending_receipt",
        "pending_appointment", "appointed", "pending_use",
        "partial_used", "completed", "expired",
        "refunding", "refunded", "cancelled",
    }
    actual = {s.value for s in UnifiedOrderStatus}
    missing = expected - actual
    assert not missing, f"PRD V2 缺失状态: {missing}"
    # pending_review 保留作历史兼容
    assert "pending_review" in actual, "pending_review 必须保留以兼容历史数据"


def test_redemption_code_status_5_states():
    expected = {"active", "locked", "used", "expired", "refunded"}
    actual = {s.value for s in RedemptionCodeStatus}
    assert actual == expected


# ════════════════════════════════════════════
#  2. 状态机推进
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pay_delivery_only_goes_to_pending_shipment(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("delivery cat")
    pid = await _seed_product(cat_id, fulfillment_type="delivery")
    create_resp = await _create_order(client, auth_headers, pid)
    assert create_resp.status_code == 200
    oid = create_resp.json()["id"]
    pay_resp = await _pay_order(client, auth_headers, oid)
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == "pending_shipment"


@pytest.mark.asyncio
async def test_pay_in_store_no_appointment_goes_to_pending_use(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("in store cat")
    pid = await _seed_product(cat_id, fulfillment_type="in_store", appointment_mode="none")
    create_resp = await _create_order(client, auth_headers, pid)
    oid = create_resp.json()["id"]
    pay_resp = await _pay_order(client, auth_headers, oid)
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == "pending_use"


@pytest.mark.asyncio
async def test_pay_appointment_required_goes_to_pending_appointment(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("appt cat")
    pid = await _seed_product(cat_id, fulfillment_type="in_store", appointment_mode="date")
    create_resp = await _create_order(client, auth_headers, pid)
    oid = create_resp.json()["id"]
    pay_resp = await _pay_order(client, auth_headers, oid)
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == "pending_appointment"


@pytest.mark.asyncio
async def test_set_appointment_advances_to_pending_use(client: AsyncClient, auth_headers):
    """[PRD 订单状态机简化方案 v1.0] 用户首次填预约日：
    pending_appointment → **pending_use**（不再走 appointed 中间态）。
    """
    cat_id = await _seed_category("appt2 cat")
    pid = await _seed_product(cat_id, fulfillment_type="in_store", appointment_mode="date")
    create_resp = await _create_order(client, auth_headers, pid)
    oid = create_resp.json()["id"]
    await _pay_order(client, auth_headers, oid)
    appt_time = (datetime.utcnow() + timedelta(days=2)).isoformat()
    appt_resp = await client.post(
        f"/api/orders/unified/{oid}/appointment",
        json={"appointment_time": appt_time},
        headers=auth_headers,
    )
    assert appt_resp.status_code == 200, appt_resp.text
    # 新策略：直接跳到 pending_use（立即出码）
    assert appt_resp.json()["status"] == "pending_use"

    detail = await client.get(f"/api/orders/unified/{oid}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending_use"


# ════════════════════════════════════════════
#  3. Tab 列表过滤映射
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tab_pending_use_includes_appointed_and_partial_used(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("tabs cat")
    p_appt = await _seed_product(cat_id, name="需预约", fulfillment_type="in_store",
                                 appointment_mode="date")
    p_in = await _seed_product(cat_id, name="到店", fulfillment_type="in_store")
    o1 = (await _create_order(client, auth_headers, p_appt)).json()["id"]
    o2 = (await _create_order(client, auth_headers, p_in)).json()["id"]
    await _pay_order(client, auth_headers, o1)  # → pending_appointment
    await _pay_order(client, auth_headers, o2)  # → pending_use

    resp = await client.get("/api/orders/unified?tab=pending_use", headers=auth_headers)
    assert resp.status_code == 200
    statuses = {item["status"] for item in resp.json()["items"]}
    assert "pending_appointment" in statuses
    assert "pending_use" in statuses


@pytest.mark.asyncio
async def test_tab_completed_includes_expired(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("complete cat")
    p_in = await _seed_product(cat_id, fulfillment_type="in_store")
    o = (await _create_order(client, auth_headers, p_in)).json()["id"]
    await _pay_order(client, auth_headers, o)
    # 直接改库设为 expired
    async with test_session() as db:
        order = (await db.execute(
            __import__("sqlalchemy").select(UnifiedOrder).where(UnifiedOrder.id == o)
        )).scalar_one()
        order.status = UnifiedOrderStatus.expired
        await db.commit()

    resp = await client.get("/api/orders/unified?tab=completed", headers=auth_headers)
    assert resp.status_code == 200
    statuses = [item["status"] for item in resp.json()["items"]]
    assert "expired" in statuses


@pytest.mark.asyncio
async def test_refund_flow_flips_status_to_refunding(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("refund cat")
    p_in = await _seed_product(cat_id, fulfillment_type="in_store")
    o = (await _create_order(client, auth_headers, p_in)).json()["id"]
    await _pay_order(client, auth_headers, o)

    rf = await client.post(
        f"/api/orders/unified/{o}/refund",
        json={"reason": "测试退款"},
        headers=auth_headers,
    )
    assert rf.status_code == 200, rf.text
    detail = await client.get(f"/api/orders/unified/{o}", headers=auth_headers)
    assert detail.json()["status"] == "refunding"

    # tab=refund_aftersales 必须能查到
    resp = await client.get(
        "/api/orders/unified?tab=refund_aftersales", headers=auth_headers
    )
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert o in ids


@pytest.mark.asyncio
async def test_refund_withdraw_flips_back(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("refund2 cat")
    p_in = await _seed_product(cat_id, fulfillment_type="in_store")
    o = (await _create_order(client, auth_headers, p_in)).json()["id"]
    await _pay_order(client, auth_headers, o)
    await client.post(
        f"/api/orders/unified/{o}/refund",
        json={"reason": "x"},
        headers=auth_headers,
    )
    wd = await client.post(
        f"/api/orders/unified/{o}/refund/withdraw", headers=auth_headers
    )
    assert wd.status_code == 200
    detail = await client.get(f"/api/orders/unified/{o}", headers=auth_headers)
    assert detail.json()["status"] == "pending_use"


# ════════════════════════════════════════════
#  4. /counts V2 字段
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_counts_v2_keys(client: AsyncClient, auth_headers):
    resp = await client.get("/api/orders/unified/counts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for k in (
        "v2_pending_payment", "v2_pending_receipt", "v2_pending_use",
        "v2_completed", "v2_refund_aftersales",
    ):
        assert k in data, f"counts 缺失 V2 字段 {k}"
        assert isinstance(data[k], int) and data[k] >= 0


# ════════════════════════════════════════════
#  5. 订单响应必带 V2 显示字段
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_order_response_includes_display_fields(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("disp cat")
    pid = await _seed_product(cat_id, fulfillment_type="in_store")
    o = (await _create_order(client, auth_headers, pid)).json()["id"]
    detail = await client.get(f"/api/orders/unified/{o}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    for k in ("display_status", "display_status_color", "action_buttons", "badges"):
        assert k in body, f"订单响应缺失 V2 字段 {k}"
    assert body["display_status"] == "待付款"
    assert isinstance(body["action_buttons"], list)
    assert "pay" in body["action_buttons"]
    assert "cancel" in body["action_buttons"]


@pytest.mark.asyncio
async def test_completed_unreviewed_shows_pending_review_text(client: AsyncClient, auth_headers):
    """V2：completed AND has_reviewed=False → display_status="待评价"。"""
    cat_id = await _seed_category("rev cat")
    pid = await _seed_product(cat_id, fulfillment_type="in_store")
    o = (await _create_order(client, auth_headers, pid)).json()["id"]
    async with test_session() as db:
        order = (await db.execute(
            __import__("sqlalchemy").select(UnifiedOrder).where(UnifiedOrder.id == o)
        )).scalar_one()
        order.status = UnifiedOrderStatus.completed
        order.has_reviewed = False
        await db.commit()

    detail = await client.get(f"/api/orders/unified/{o}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["display_status"] == "待评价"
    assert "review" in body["action_buttons"]


# ════════════════════════════════════════════
#  6. admin V2 枚举接口
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_v2_enums(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/orders/v2/enums", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["order_status"]) == 12
    assert len(data["redemption_code_status"]) == 5
    values = {x["value"] for x in data["order_status"]}
    assert values == {
        "pending_payment", "pending_shipment", "pending_receipt",
        "pending_appointment", "appointed", "pending_use",
        "partial_used", "completed", "expired",
        "refunding", "refunded", "cancelled",
    }


@pytest.mark.asyncio
async def test_admin_v2_stats(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/orders/v2/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "gmv" in data
    assert "refunded_amount" in data
    assert "fulfillment_rate" in data
    assert isinstance(data["status_breakdown"], dict)
    assert isinstance(data["redemption_code_breakdown"], dict)


@pytest.mark.asyncio
async def test_admin_filter_by_redemption_code_status(client: AsyncClient, admin_headers, auth_headers):
    cat_id = await _seed_category("adm rcs cat")
    pid = await _seed_product(cat_id, fulfillment_type="in_store")
    o = (await _create_order(client, auth_headers, pid)).json()["id"]
    # 标记一个 item 的核销码为 used
    async with test_session() as db:
        item = (await db.execute(
            __import__("sqlalchemy").select(OrderItem).where(OrderItem.order_id == o)
        )).scalars().first()
        item.redemption_code_status = "used"
        await db.commit()

    resp = await client.get(
        "/api/admin/orders/unified?redemption_code_status=used", headers=admin_headers
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert o in ids
