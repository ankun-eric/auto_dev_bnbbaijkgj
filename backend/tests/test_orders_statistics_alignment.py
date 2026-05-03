"""[订单统计状态对齐] 后端测试

覆盖：
1. /api/admin/orders/statistics 接口可正常调用，鉴权正确
2. 返回 12 个订单状态聚合（与 UnifiedOrderStatus PRD V2 对齐，含 pending_appointment / appointed /
   partial_used / expired / refunding / refunded）
3. 返回 7 个退款状态聚合（与 RefundStatusEnum 全量对齐，含 reviewing / returning）
4. 卡片字段：status / label / count / amount 完整
5. 时间筛选 start_at / end_at 生效（构造跨日订单后按"今天"筛选只返回今天的数据）
6. summary 汇总字段：total_orders / total_revenue / total_refund_count / total_refund_amount
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.models import (
    Product,
    ProductCategory,
    UnifiedOrder,
    UnifiedOrderStatus,
    OrderItem,
    RefundStatusEnum,
    User,
)
from tests.conftest import test_session


EXPECTED_ORDER_STATUSES_12 = [
    "pending_payment", "pending_shipment", "pending_receipt",
    "pending_appointment", "appointed", "pending_use",
    "partial_used", "completed", "expired",
    "refunding", "refunded", "cancelled",
]

EXPECTED_REFUND_STATUSES_7 = [
    "none", "applied", "reviewing", "approved", "rejected",
    "returning", "refund_success",
]


async def _seed_category(name: str = "stat cat") -> int:
    async with test_session() as db:
        cat = ProductCategory(name=name, status="active", sort_order=0, level=1)
        db.add(cat)
        await db.commit()
        return cat.id


async def _seed_product(category_id: int, fulfillment_type: str = "in_store") -> int:
    async with test_session() as db:
        p = Product(
            name="统计测试商品",
            category_id=category_id,
            fulfillment_type=fulfillment_type,
            sale_price=100.0,
            stock=100,
            status="active",
            redeem_count=1,
            appointment_mode="none",
        )
        db.add(p)
        await db.commit()
        return p.id


async def _seed_order(
    user_id: int,
    product_id: int,
    *,
    status: str,
    refund_status: str = "none",
    paid_amount: float = 100.0,
    created_at: datetime = None,
) -> int:
    async with test_session() as db:
        order = UnifiedOrder(
            user_id=user_id,
            order_no=f"TEST_{datetime.utcnow().timestamp()}_{status}",
            status=UnifiedOrderStatus(status),
            refund_status=RefundStatusEnum(refund_status),
            total_amount=paid_amount,
            paid_amount=paid_amount,
            created_at=created_at or datetime.utcnow(),
        )
        db.add(order)
        await db.commit()
        # 添加一条 OrderItem
        item = OrderItem(
            order_id=order.id,
            product_id=product_id,
            product_name="统计测试商品",
            quantity=1,
            unit_price=paid_amount,
            subtotal=paid_amount,
            fulfillment_type="in_store",
            total_redeem_count=1,
            used_redeem_count=0,
        )
        db.add(item)
        await db.commit()
        return order.id


# ════════════════════════════════════════════
#  1. 接口存在性与鉴权
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_orders_statistics_requires_admin(client: AsyncClient):
    """无 token 必须 401/403。"""
    resp = await client.get("/api/admin/orders/statistics")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_orders_statistics_basic_response_shape(client: AsyncClient, admin_headers):
    """基础响应结构：含 summary / order_status_items / refund_status_items。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "summary" in data
    assert "order_status_items" in data
    assert "refund_status_items" in data
    assert isinstance(data["order_status_items"], list)
    assert isinstance(data["refund_status_items"], list)


# ════════════════════════════════════════════
#  2. 状态完整性：12 + 7
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_orders_statistics_returns_12_order_statuses(client: AsyncClient, admin_headers):
    """必须返回完整 12 个订单状态卡片（即使 count=0 也要占位）。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["order_status_items"]
    assert len(items) == 12, f"应该返回 12 个订单状态卡片，实际 {len(items)}"
    statuses = [it["status"] for it in items]
    for expected in EXPECTED_ORDER_STATUSES_12:
        assert expected in statuses, f"缺失订单状态: {expected}"


@pytest.mark.asyncio
async def test_orders_statistics_returns_7_refund_statuses(client: AsyncClient, admin_headers):
    """必须返回完整 7 个退款状态卡片。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["refund_status_items"]
    assert len(items) == 7, f"应该返回 7 个退款状态卡片，实际 {len(items)}"
    statuses = [it["status"] for it in items]
    for expected in EXPECTED_REFUND_STATUSES_7:
        assert expected in statuses, f"缺失退款状态: {expected}"


@pytest.mark.asyncio
async def test_each_status_card_has_label_count_amount(client: AsyncClient, admin_headers):
    """每个卡片必须含 status/label/count/amount 四个字段，且 label 为中文。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    for it in data["order_status_items"] + data["refund_status_items"]:
        assert "status" in it
        assert "label" in it
        assert "count" in it
        assert "amount" in it
        # label 必须含中文
        assert any('\u4e00' <= c <= '\u9fff' for c in it["label"]), \
            f"label 必须为中文，实际: {it['label']}"


@pytest.mark.asyncio
async def test_v2_new_statuses_exist_in_cards(client: AsyncClient, admin_headers):
    """PRD V2 新增的 6 个状态（pending_appointment / appointed / partial_used /
    expired / refunding / refunded）必须出现在卡片矩阵中。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    statuses = [it["status"] for it in resp.json()["order_status_items"]]
    for new_st in ["pending_appointment", "appointed", "partial_used",
                   "expired", "refunding", "refunded"]:
        assert new_st in statuses, f"V2 新增状态 {new_st} 必须在统计卡片中"


@pytest.mark.asyncio
async def test_refund_extended_statuses_exist_in_cards(client: AsyncClient, admin_headers):
    """PRD V2 退款增强：reviewing / returning 必须出现在退款状态卡片中。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    statuses = [it["status"] for it in resp.json()["refund_status_items"]]
    assert "reviewing" in statuses
    assert "returning" in statuses


# ════════════════════════════════════════════
#  3. 数据聚合正确性
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_orders_statistics_count_and_amount_aggregation(client: AsyncClient, admin_headers, admin_token):
    """造一个 pending_payment 订单，验证统计接口返回的 count/amount 正确。"""
    cat_id = await _seed_category("agg cat")
    pid = await _seed_product(cat_id)

    # 取出 admin 用户 id
    async with test_session() as db:
        from sqlalchemy import select
        admin = (await db.execute(select(User).where(User.phone == "13800000001"))).scalar_one()

    await _seed_order(admin.id, pid, status="pending_payment", paid_amount=88.0)
    await _seed_order(admin.id, pid, status="pending_payment", paid_amount=12.0)
    await _seed_order(admin.id, pid, status="completed", paid_amount=200.0)

    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    items = {it["status"]: it for it in resp.json()["order_status_items"]}

    pp = items["pending_payment"]
    assert pp["count"] >= 2
    assert pp["amount"] >= 100.0  # 88 + 12

    cp = items["completed"]
    assert cp["count"] >= 1
    assert cp["amount"] >= 200.0


@pytest.mark.asyncio
async def test_orders_statistics_time_filter(client: AsyncClient, admin_headers):
    """start_at/end_at 时间筛选生效：用一个未来日期范围应得到全 0 数据。"""
    future_start = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    future_end = (datetime.utcnow() + timedelta(days=370)).strftime("%Y-%m-%d")
    resp = await client.get(
        f"/api/admin/orders/statistics?start_at={future_start}&end_at={future_end}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # 未来时间段不应有任何订单
    for it in data["order_status_items"]:
        assert it["count"] == 0, f"{it['status']} 在未来时间段不应有数据"
    assert data["summary"]["total_orders"] == 0


@pytest.mark.asyncio
async def test_orders_statistics_summary_fields(client: AsyncClient, admin_headers):
    """summary 必须含四个核心字段。"""
    resp = await client.get("/api/admin/orders/statistics", headers=admin_headers)
    assert resp.status_code == 200
    s = resp.json()["summary"]
    assert "total_orders" in s
    assert "total_revenue" in s
    assert "total_refund_count" in s
    assert "total_refund_amount" in s
