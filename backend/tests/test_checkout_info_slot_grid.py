"""[PRD v1.0 2026-05-04 用户端下单页时段网格化展示与满额置灰]

覆盖 `/api/h5/checkout/info` 接口与 `/api/h5/slots` 接口对满额标记字段的支持。
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.models import (
    AppointmentMode,
    FulfillmentType,
    MerchantStore,
    OrderItem,
    Product,
    ProductCategory,
    ProductStatus,
    ProductStore,
    PurchaseAppointmentMode,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from tests.conftest import test_session


@pytest_asyncio.fixture
async def time_slot_product_with_store(user_token):
    """创建一个 time_slot 模式商品 + 一个门店并建立 product_store 绑定。

    商品时段：09:00-10:00 (cap=2), 10:00-11:00 (cap=0 表示不限制), 11:00-12:00 (cap=2)
    门店容量：5
    """
    async with test_session() as session:
        category = ProductCategory(name="按摩")
        session.add(category)
        await session.flush()

        store = MerchantStore(
            store_name="测试门店",
            store_code="TEST_STORE_GRID",
            status="active",
            slot_capacity=5,
            business_start="08:00",
            business_end="20:00",
        )
        session.add(store)
        await session.flush()

        product = Product(
            name="测试时段商品",
            category_id=category.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=Decimal("100.00"),
            stock=100,
            appointment_mode=AppointmentMode.time_slot,
            purchase_appointment_mode=PurchaseAppointmentMode.purchase_with_appointment,
            advance_days=7,
            include_today=True,
            time_slots=[
                {"start": "09:00", "end": "10:00", "capacity": 2},
                {"start": "10:00", "end": "11:00", "capacity": 0},  # 商品级不限制
                {"start": "11:00", "end": "12:00", "capacity": 2},
            ],
            status=ProductStatus.published if hasattr(ProductStatus, "published") else ProductStatus.draft,
        )
        session.add(product)
        await session.flush()

        ps = ProductStore(product_id=product.id, store_id=store.id)
        session.add(ps)
        await session.commit()
        return {
            "product_id": product.id,
            "store_id": store.id,
        }


async def _make_user_id(phone: str = "13900000001") -> int:
    async with test_session() as session:
        from sqlalchemy import select
        res = await session.execute(select(User).where(User.phone == phone))
        u = res.scalar_one_or_none()
        return u.id if u else 0


async def _add_paid_order_for_slot(
    user_id: int,
    product_id: int,
    store_id: int,
    target_date: date,
    slot_label: str,
    *,
    status: UnifiedOrderStatus = UnifiedOrderStatus.pending_use,
    created_offset_minutes: int = 0,
):
    """插入一条占用某时段的 UnifiedOrder + OrderItem。"""
    async with test_session() as session:
        from sqlalchemy import func
        order = UnifiedOrder(
            order_no=f"TEST_{target_date.isoformat()}_{slot_label}_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            total_amount=Decimal("100.00"),
            paid_amount=Decimal("100.00"),
            status=status,
            store_id=store_id,
            created_at=datetime.utcnow() + timedelta(minutes=created_offset_minutes),
        )
        session.add(order)
        await session.flush()

        start_str = slot_label.split("-")[0]
        appt_dt = datetime.combine(target_date, datetime.strptime(start_str, "%H:%M").time())
        item = OrderItem(
            order_id=order.id,
            product_id=product_id,
            product_name="测试商品",
            product_price=Decimal("100.00"),
            quantity=1,
            subtotal=Decimal("100.00"),
            fulfillment_type=FulfillmentType.in_store,
            appointment_time=appt_dt,
            appointment_data={"date": target_date.isoformat(), "time_slot": slot_label},
        )
        session.add(item)
        await session.commit()


@pytest.mark.asyncio
async def test_checkout_info_returns_available_slots_with_is_available(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §6.2] /checkout/info 应返回 `available_slots`，每条带 `is_available` + `unavailable_reason`。"""
    pid = time_slot_product_with_store["product_id"]
    res = await client.get(f"/api/h5/checkout/info?productId={pid}", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["product_id"] == pid
    assert data["appointment_mode"] == "time_slot"
    slots = data["available_slots"]
    assert len(slots) == 3
    for s in slots:
        assert "is_available" in s and "unavailable_reason" in s
        assert "start_time" in s and "end_time" in s
    # 没有占用订单时全部可用
    assert all(s["is_available"] is True for s in slots)
    assert all(s["unavailable_reason"] is None for s in slots)


@pytest.mark.asyncio
async def test_product_capacity_full_marks_slot_unavailable(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §5.1] 商品级 capacity=2 已被 2 单占用 → is_available=false, reason=occupied。"""
    pid = time_slot_product_with_store["product_id"]
    sid = time_slot_product_with_store["store_id"]
    user_id = await _make_user_id()
    today = date.today()
    target = today + timedelta(days=1)
    # 09:00-10:00 capacity=2
    for _ in range(2):
        await _add_paid_order_for_slot(user_id, pid, sid, target, "09:00-10:00")

    res = await client.get(
        f"/api/h5/checkout/info?productId={pid}&storeId={sid}&date={target.isoformat()}",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    slots = res.json()["data"]["available_slots"]
    s0900 = next(s for s in slots if s["start_time"] == "09:00")
    assert s0900["is_available"] is False
    assert s0900["unavailable_reason"] == "occupied"
    # 其它时段仍可约
    s1100 = next(s for s in slots if s["start_time"] == "11:00")
    assert s1100["is_available"] is True


@pytest.mark.asyncio
async def test_store_capacity_full_marks_slot_unavailable_cross_product(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §5.1] 门店级 slot_capacity=5 被同时段累计 5 单占用 → 即便商品级未满也置灰。

    验证「门店级是跨商品累计」：用同 product_id 占满 5 单（门店容量 5），
    其它时段 capacity=0（不限制商品）也应被标记为 occupied。
    """
    pid = time_slot_product_with_store["product_id"]
    sid = time_slot_product_with_store["store_id"]
    user_id = await _make_user_id()
    target = date.today() + timedelta(days=1)
    # 10:00-11:00 商品级容量=0（不限制），但门店容量=5 → 占 5 单后门店级满
    for _ in range(5):
        await _add_paid_order_for_slot(user_id, pid, sid, target, "10:00-11:00")

    res = await client.get(
        f"/api/h5/checkout/info?productId={pid}&storeId={sid}&date={target.isoformat()}",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    slots = res.json()["data"]["available_slots"]
    s1000 = next(s for s in slots if s["start_time"] == "10:00")
    assert s1000["is_available"] is False
    assert s1000["unavailable_reason"] == "occupied"


@pytest.mark.asyncio
async def test_pending_payment_within_15min_counts_as_occupied(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §5.3] 15 分钟内的 pending_payment 订单 → 计入占用。"""
    pid = time_slot_product_with_store["product_id"]
    sid = time_slot_product_with_store["store_id"]
    user_id = await _make_user_id()
    target = date.today() + timedelta(days=1)
    # 09:00-10:00 capacity=2，写两单 pending_payment（刚创建）
    for _ in range(2):
        await _add_paid_order_for_slot(
            user_id, pid, sid, target, "09:00-10:00",
            status=UnifiedOrderStatus.pending_payment,
            created_offset_minutes=0,
        )
    res = await client.get(
        f"/api/h5/checkout/info?productId={pid}&storeId={sid}&date={target.isoformat()}",
        headers=auth_headers,
    )
    slots = res.json()["data"]["available_slots"]
    s0900 = next(s for s in slots if s["start_time"] == "09:00")
    assert s0900["is_available"] is False


@pytest.mark.asyncio
async def test_pending_payment_over_15min_does_not_count_as_occupied(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §5.3] 超过 15 分钟未支付的 pending_payment → 不计入占用。"""
    pid = time_slot_product_with_store["product_id"]
    sid = time_slot_product_with_store["store_id"]
    user_id = await _make_user_id()
    target = date.today() + timedelta(days=1)
    # 09:00-10:00 capacity=2，写两单 pending_payment 但 created_at 是 16 分钟前
    for _ in range(2):
        await _add_paid_order_for_slot(
            user_id, pid, sid, target, "09:00-10:00",
            status=UnifiedOrderStatus.pending_payment,
            created_offset_minutes=-16,
        )
    res = await client.get(
        f"/api/h5/checkout/info?productId={pid}&storeId={sid}&date={target.isoformat()}",
        headers=auth_headers,
    )
    slots = res.json()["data"]["available_slots"]
    s0900 = next(s for s in slots if s["start_time"] == "09:00")
    assert s0900["is_available"] is True


@pytest.mark.asyncio
async def test_cancelled_order_does_not_count_as_occupied(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §5.3] 已取消订单不计入占用。"""
    pid = time_slot_product_with_store["product_id"]
    sid = time_slot_product_with_store["store_id"]
    user_id = await _make_user_id()
    target = date.today() + timedelta(days=1)
    for _ in range(2):
        await _add_paid_order_for_slot(
            user_id, pid, sid, target, "09:00-10:00",
            status=UnifiedOrderStatus.cancelled,
        )
    res = await client.get(
        f"/api/h5/checkout/info?productId={pid}&storeId={sid}&date={target.isoformat()}",
        headers=auth_headers,
    )
    slots = res.json()["data"]["available_slots"]
    s0900 = next(s for s in slots if s["start_time"] == "09:00")
    assert s0900["is_available"] is True


@pytest.mark.asyncio
async def test_slots_endpoint_now_returns_full_slots_with_marker(
    client: AsyncClient, auth_headers, time_slot_product_with_store,
):
    """[PRD §4.1.1] `/api/h5/slots` 改造后：满额时段不再过滤而是返回 is_available=false。"""
    pid = time_slot_product_with_store["product_id"]
    sid = time_slot_product_with_store["store_id"]
    user_id = await _make_user_id()
    target = date.today() + timedelta(days=1)
    for _ in range(2):
        await _add_paid_order_for_slot(user_id, pid, sid, target, "09:00-10:00")

    res = await client.get(
        f"/api/h5/slots?storeId={sid}&date={target.isoformat()}&productId={pid}",
        headers=auth_headers,
    )
    assert res.status_code == 200
    slots = res.json()["data"]["slots"]
    # 满额时段也应在列表中（不再被过滤）
    labels = [s["label"] for s in slots]
    assert "09:00-10:00" in labels
    s0900 = next(s for s in slots if s["label"] == "09:00-10:00")
    assert s0900["is_available"] is False
    assert s0900["unavailable_reason"] == "occupied"


@pytest.mark.asyncio
async def test_checkout_info_unauth_returns_401(client: AsyncClient, time_slot_product_with_store):
    """未登录访问应返回 401。"""
    pid = time_slot_product_with_store["product_id"]
    res = await client.get(f"/api/h5/checkout/info?productId={pid}")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_checkout_info_404_when_product_not_exist(client: AsyncClient, auth_headers):
    """商品不存在 → 404。"""
    res = await client.get("/api/h5/checkout/info?productId=999999", headers=auth_headers)
    assert res.status_code == 404
