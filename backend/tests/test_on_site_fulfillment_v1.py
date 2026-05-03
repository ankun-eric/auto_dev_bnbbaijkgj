"""[上门服务履约 PRD v1.0] 自动化测试

覆盖：
1. FulfillmentType 枚举包含 on_site
2. UnifiedOrder 新增 service_address_id / service_address_snapshot 字段
3. 商品级 + 门店级双层名额校验：商品级满 → 拒绝；门店级满 → 拒绝；都未配置 → 通过
4. 商品时段 capacity 允许为 None（不限）
5. 上门服务订单未传 service_address_id → 拒绝
6. 上门服务订单地址快照写入正确
"""
from datetime import datetime, timedelta, date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.models.models import (
    AppointmentMode,
    FulfillmentType,
    MerchantStore,
    OrderItem,
    Product,
    ProductStatus,
    ProductCategory,
    ProductStore,
    PurchaseAppointmentMode,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserAddress,
    UserRole,
)
from app.core.security import get_password_hash


def test_fulfillment_type_has_on_site():
    """枚举包含 on_site 值"""
    assert FulfillmentType.on_site.value == "on_site"
    values = {ft.value for ft in FulfillmentType}
    assert {"in_store", "delivery", "virtual", "on_site"}.issubset(values)


def test_unified_order_has_service_address_columns():
    """UnifiedOrder 新增 service_address_id / service_address_snapshot 列"""
    cols = {c.name for c in UnifiedOrder.__table__.columns}
    assert "service_address_id" in cols
    assert "service_address_snapshot" in cols


@pytest_asyncio.fixture
async def buyer_token(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13900099001",
        "password": "user123",
        "nickname": "上门测试用户",
    })
    res = await client.post("/api/auth/login", json={
        "phone": "13900099001",
        "password": "user123",
    })
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def buyer_headers(buyer_token):
    return {"Authorization": f"Bearer {buyer_token}"}


async def _seed_user_address(user_id: int, name: str = "张三") -> int:
    async with test_session() as session:
        addr = UserAddress(
            user_id=user_id,
            name=name,
            phone="13800000000",
            province="广东",
            city="深圳",
            district="南山",
            street="科技园北区 8 号楼 101",
            is_default=True,
        )
        session.add(addr)
        await session.commit()
        await session.refresh(addr)
        return addr.id


async def _seed_on_site_product(*, slot_capacity_store: int = 5,
                                product_slot_cap=None,
                                appt_mode="time_slot") -> tuple[int, int]:
    """创建上门服务商品 + 门店；返回 (product_id, store_id)。"""
    async with test_session() as session:
        cat = ProductCategory(name="上门服务", level=1, status="active")
        session.add(cat)
        await session.flush()
        store = MerchantStore(
            store_code="MD00001",
            store_name="测试门店",
            slot_capacity=slot_capacity_store,
            business_start="09:00",
            business_end="22:00",
        )
        session.add(store)
        await session.flush()
        slots = [
            {"start": "09:00", "end": "10:00", "capacity": product_slot_cap},
            {"start": "10:00", "end": "11:00", "capacity": product_slot_cap},
        ]
        prod = Product(
            name="上门保养服务",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.on_site,
            sale_price=100,
            stock=999,
            status=ProductStatus.active,
            appointment_mode=AppointmentMode(appt_mode),
            purchase_appointment_mode=PurchaseAppointmentMode.purchase_with_appointment,
            advance_days=7,
            time_slots=slots,
            include_today=True,
            spec_mode=1,
        )
        session.add(prod)
        await session.flush()
        ps = ProductStore(product_id=prod.id, store_id=store.id)
        session.add(ps)
        await session.commit()
        return prod.id, store.id


async def _get_buyer_id() -> int:
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900099001"))
        u = res.scalar_one()
        return u.id


@pytest.mark.asyncio
async def test_on_site_order_requires_service_address(client: AsyncClient, buyer_headers):
    """上门服务商品下单未传 service_address_id 必须被拒绝。"""
    prod_id, store_id = await _seed_on_site_product()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "items": [{
            "product_id": prod_id,
            "quantity": 1,
            "appointment_data": {
                "store_id": store_id,
                "date": tomorrow,
                "time_slot": "09:00-10:00",
            },
            "appointment_time": f"{tomorrow}T09:00:00",
        }],
        "payment_method": "wechat",
    }
    res = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res.status_code == 400
    assert "上门" in res.json().get("detail", "") or "地址" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_on_site_order_with_address_creates_snapshot(client: AsyncClient, buyer_headers):
    """上门服务订单成功创建后，service_address_id + 快照应被写入。"""
    prod_id, store_id = await _seed_on_site_product(slot_capacity_store=5)
    user_id = await _get_buyer_id()
    addr_id = await _seed_user_address(user_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "items": [{
            "product_id": prod_id,
            "quantity": 1,
            "appointment_data": {
                "store_id": store_id,
                "date": tomorrow,
                "time_slot": "09:00-10:00",
            },
            "appointment_time": f"{tomorrow}T09:00:00",
        }],
        "payment_method": "wechat",
        "service_address_id": addr_id,
    }
    res = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res.status_code in (200, 201), res.text
    body = res.json()
    assert body.get("service_address_id") == addr_id
    snapshot = body.get("service_address_snapshot")
    assert snapshot is not None
    assert snapshot.get("name") == "张三"
    assert snapshot.get("province") == "广东"
    assert snapshot.get("phone") == "13800000000"


@pytest.mark.asyncio
async def test_product_level_quota_blocks_when_full(client: AsyncClient, buyer_headers):
    """商品级名额（time_slots[].capacity=1）已满时应拒绝下单。"""
    prod_id, store_id = await _seed_on_site_product(
        slot_capacity_store=10, product_slot_cap=1
    )
    user_id = await _get_buyer_id()
    addr_id = await _seed_user_address(user_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "items": [{
            "product_id": prod_id,
            "quantity": 1,
            "appointment_data": {
                "store_id": store_id,
                "date": tomorrow,
                "time_slot": "09:00-10:00",
            },
            "appointment_time": f"{tomorrow}T09:00:00",
        }],
        "payment_method": "wechat",
        "service_address_id": addr_id,
    }
    # 第一次：成功（占用 1/1）
    res1 = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res1.status_code in (200, 201), res1.text

    # 第二次：商品级满，应拒绝
    res2 = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res2.status_code == 400
    assert "约满" in res2.json().get("detail", "")


@pytest.mark.asyncio
async def test_store_level_quota_blocks_when_full(client: AsyncClient, buyer_headers):
    """门店级名额（slot_capacity=1）已满时应拒绝下单（即使商品级未配置）。"""
    prod_id, store_id = await _seed_on_site_product(
        slot_capacity_store=1, product_slot_cap=None
    )
    user_id = await _get_buyer_id()
    addr_id = await _seed_user_address(user_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "items": [{
            "product_id": prod_id,
            "quantity": 1,
            "appointment_data": {
                "store_id": store_id,
                "date": tomorrow,
                "time_slot": "09:00-10:00",
            },
            "appointment_time": f"{tomorrow}T09:00:00",
        }],
        "payment_method": "wechat",
        "service_address_id": addr_id,
    }
    # 第一次：成功
    res1 = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res1.status_code in (200, 201), res1.text

    # 第二次：门店级满
    res2 = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res2.status_code == 400
    assert "约满" in res2.json().get("detail", "")


@pytest.mark.asyncio
async def test_no_quota_configured_allows_unlimited_orders(client: AsyncClient, buyer_headers):
    """商品级 capacity=None + 门店级 slot_capacity=0 → 不限流，可连续下单。"""
    # slot_capacity=0 表示不限（PRD 双不填即不限流）
    prod_id, store_id = await _seed_on_site_product(
        slot_capacity_store=0, product_slot_cap=None
    )
    user_id = await _get_buyer_id()
    addr_id = await _seed_user_address(user_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "items": [{
            "product_id": prod_id,
            "quantity": 1,
            "appointment_data": {
                "store_id": store_id,
                "date": tomorrow,
                "time_slot": "09:00-10:00",
            },
            "appointment_time": f"{tomorrow}T09:00:00",
        }],
        "payment_method": "wechat",
        "service_address_id": addr_id,
    }
    for _ in range(3):
        r = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
        assert r.status_code in (200, 201), r.text


@pytest.mark.asyncio
async def test_on_site_order_address_must_belong_to_user(client: AsyncClient, buyer_headers):
    """传入他人地址 ID 应被拒绝。"""
    prod_id, store_id = await _seed_on_site_product()
    # 地址挂在另一个用户身上
    async with test_session() as s:
        other = User(
            phone="13900099999",
            password_hash=get_password_hash("x"),
            nickname="other",
            role=UserRole.user,
        )
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    other_addr = await _seed_user_address(other_id, name="李四")

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "items": [{
            "product_id": prod_id,
            "quantity": 1,
            "appointment_data": {
                "store_id": store_id,
                "date": tomorrow,
                "time_slot": "09:00-10:00",
            },
            "appointment_time": f"{tomorrow}T09:00:00",
        }],
        "payment_method": "wechat",
        "service_address_id": other_addr,
    }
    res = await client.post("/api/orders/unified", headers=buyer_headers, json=payload)
    assert res.status_code == 400
    assert "不存在" in res.json().get("detail", "") or "属于" in res.json().get("detail", "")
