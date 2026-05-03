"""[2026-05-02 H5 下单流程优化 PRD v1.0] 自动化测试

覆盖：
1. 门店新建/编辑可保存 slot_capacity / business_start / business_end 字段（默认 10）
2. /api/h5/checkout/init 返回日期范围 + 默认门店 + 联系人手机号
3. /api/h5/slots 返回时段（商品时段 ∩ 门店营业时段，且排除已满档）
4. /api/h5/slots 商品时段不在门店营业时段时被过滤
5. /api/h5/slots 已满档时段被隐藏（不在返回列表中）
6. available-stores 响应附带 slot_capacity / business_start / business_end
"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.models.models import (
    AppointmentMode,
    FulfillmentType,
    MerchantCategory,
    MerchantStore,
    OrderItem,
    Product,
    ProductStore,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from app.core.security import get_password_hash


@pytest_asyncio.fixture
async def cat_id():
    async with test_session() as session:
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat.id


@pytest_asyncio.fixture
async def normal_user_token(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13900000099",
        "password": "user123",
        "nickname": "下单测试用户",
    })
    res = await client.post("/api/auth/login", json={
        "phone": "13900000099",
        "password": "user123",
    })
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def normal_user_headers(normal_user_token):
    return {"Authorization": f"Bearer {normal_user_token}"}


async def _seed_product_with_stores(
    *,
    advance_days: int = 7,
    include_today: bool = True,
    time_slots: list[dict] | None = None,
    store_count: int = 1,
    business_start: str | None = "09:00",
    business_end: str | None = "22:00",
    slot_capacity: int = 10,
    cat_id: int | None = None,
):
    if time_slots is None:
        time_slots = [{"start": "09:00", "end": "11:00"}, {"start": "14:00", "end": "16:00"}]
    async with test_session() as session:
        product = Product(
            name="预约时段优化测试商品",
            sale_price=100,
            stock=999,
            fulfillment_type=FulfillmentType.in_store,
            appointment_mode=AppointmentMode.time_slot,
            advance_days=advance_days,
            include_today=include_today,
            time_slots=time_slots,
            status="active",
        )
        session.add(product)
        await session.flush()

        store_ids = []
        for i in range(store_count):
            store = MerchantStore(
                store_name=f"测试门店 {i+1}",
                store_code=f"MD{i+99001:05d}",
                category_id=cat_id,
                status="active",
                lat=23.0 + i * 0.001,
                lng=113.0 + i * 0.001,
                slot_capacity=slot_capacity,
                business_start=business_start,
                business_end=business_end,
            )
            session.add(store)
            await session.flush()
            store_ids.append(store.id)
            session.add(ProductStore(product_id=product.id, store_id=store.id))
        await session.commit()
        await session.refresh(product)
        return product.id, store_ids


# ────────────────── Test 1：门店字段往返 ──────────────────


@pytest.mark.asyncio
async def test_store_capacity_and_business_hours_round_trip(
    client: AsyncClient, admin_headers, cat_id
):
    """新建/编辑门店时，slot_capacity / business_start / business_end 可保存并取回。"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "测试门店容量",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "slot_capacity": 20,
            "business_start": "08:30",
            "business_end": "20:00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    sid = res.json()["id"]

    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    body = detail.json()
    assert body["slot_capacity"] == 20
    assert body["business_start"] == "08:30"
    assert body["business_end"] == "20:00"

    # 编辑
    upd = await client.put(
        f"/api/admin/merchant/stores/{sid}",
        json={"slot_capacity": 5, "business_start": "10:00", "business_end": "21:00"},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    detail2 = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    body2 = detail2.json()
    assert body2["slot_capacity"] == 5
    assert body2["business_start"] == "10:00"
    assert body2["business_end"] == "21:00"


# ────────────────── Test 2：默认 slot_capacity = 10 ──────────────────


@pytest.mark.asyncio
async def test_store_default_slot_capacity_is_10(
    client: AsyncClient, admin_headers, cat_id
):
    # [2026-05-03] 营业时间已成必填项，默认值测试需补传 business_start/end
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "默认容量门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    sid = res.json()["id"]
    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    assert detail.json()["slot_capacity"] == 10


# ────────────────── Test 3：/api/h5/checkout/init ──────────────────


@pytest.mark.asyncio
async def test_h5_checkout_init_returns_full_payload(
    client: AsyncClient, normal_user_headers, cat_id
):
    pid, store_ids = await _seed_product_with_stores(
        advance_days=7, include_today=True, store_count=1, cat_id=cat_id,
    )
    res = await client.get(
        f"/api/h5/checkout/init?productId={pid}",
        headers=normal_user_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["product_id"] == pid
    # 日期范围应有 7 天
    dr = data["date_range"]
    assert dr["advance_days"] == 7
    assert dr["include_today"] is True
    assert dr["start"] is not None and dr["end"] is not None
    # 默认门店
    assert data["default_store"] is not None
    assert data["default_store"]["id"] == store_ids[0]
    assert data["default_store"]["slot_capacity"] == 10
    # 时段（不应包含 capacity）
    assert isinstance(data["available_slots"], list)
    if data["available_slots"]:
        assert "capacity" not in data["available_slots"][0]
    # 联系人手机号（默认从账户取）
    assert data["contact_phone"] == "13900000099"


# ────────────────── Test 4：/api/h5/slots 营业时段过滤 ──────────────────


@pytest.mark.asyncio
async def test_h5_slots_filter_by_business_hours(
    client: AsyncClient, cat_id
):
    """商品时段必须落在门店营业时段之内才纳入候选。"""
    pid, store_ids = await _seed_product_with_stores(
        advance_days=7,
        time_slots=[
            {"start": "08:00", "end": "10:00"},  # 不在营业（早于 09:00 开始）
            {"start": "10:00", "end": "12:00"},  # 落在 09:00-22:00
            {"start": "20:00", "end": "23:00"},  # 不在营业（晚于 22:00 结束）
        ],
        business_start="09:00",
        business_end="22:00",
        cat_id=cat_id,
    )
    today = datetime.utcnow().date().isoformat()
    res = await client.get(f"/api/h5/slots?storeId={store_ids[0]}&date={today}&productId={pid}")
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    labels = [s["label"] for s in data["slots"]]
    assert "10:00-12:00" in labels
    assert "08:00-10:00" not in labels
    assert "20:00-23:00" not in labels


# ────────────────── Test 5：/api/h5/slots 满档时段被隐藏 ──────────────────


@pytest.mark.asyncio
async def test_h5_slots_hide_full(
    client: AsyncClient, cat_id
):
    """已满档的时段不应出现在返回列表中。"""
    pid, store_ids = await _seed_product_with_stores(
        advance_days=7,
        time_slots=[
            {"start": "10:00", "end": "12:00"},
            {"start": "14:00", "end": "16:00"},
        ],
        business_start="09:00",
        business_end="22:00",
        slot_capacity=2,  # 故意设小，方便填满
        cat_id=cat_id,
    )
    target_date = datetime.utcnow().date()
    target_date_str = target_date.isoformat()
    sid = store_ids[0]

    # 给 10:00-12:00 创建 2 张已支付订单 → 满档
    async with test_session() as session:
        for i in range(2):
            user = User(
                phone=f"1399000{i:04d}",
                password_hash=get_password_hash("test123"),
                nickname=f"满档用户{i}",
                role=UserRole.normal,
            )
            session.add(user)
            await session.flush()
            order = UnifiedOrder(
                order_no=f"UO{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{i:03d}",
                user_id=user.id,
                total_amount=100,
                paid_amount=100,
                status=UnifiedOrderStatus.pending_use,
                store_id=sid,
            )
            session.add(order)
            await session.flush()
            session.add(OrderItem(
                order_id=order.id,
                product_id=pid,
                product_name="测试",
                product_price=100,
                quantity=1,
                subtotal=100,
                fulfillment_type=FulfillmentType.in_store,
                appointment_data={"date": target_date_str, "time_slot": "10:00-12:00"},
                appointment_time=datetime.combine(target_date, datetime.min.time()).replace(hour=10),
            ))
        await session.commit()

    res = await client.get(f"/api/h5/slots?storeId={sid}&date={target_date_str}&productId={pid}")
    assert res.status_code == 200
    labels = [s["label"] for s in res.json()["data"]["slots"]]
    assert "10:00-12:00" not in labels  # 满档隐藏
    assert "14:00-16:00" in labels


# ────────────────── Test 6：available-stores 返回容量字段 ──────────────────


@pytest.mark.asyncio
async def test_available_stores_returns_capacity(
    client: AsyncClient, cat_id
):
    pid, store_ids = await _seed_product_with_stores(
        advance_days=7, store_count=1, slot_capacity=15,
        business_start="08:00", business_end="23:00", cat_id=cat_id,
    )
    res = await client.get(f"/api/products/{pid}/available-stores")
    assert res.status_code == 200
    stores = res.json()["data"]["stores"]
    assert len(stores) >= 1
    s0 = stores[0]
    assert s0["slot_capacity"] == 15
    assert s0["business_start"] == "08:00"
    assert s0["business_end"] == "23:00"
