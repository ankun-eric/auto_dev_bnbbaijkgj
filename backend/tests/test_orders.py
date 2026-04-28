import pytest
from httpx import AsyncClient

from app.models.models import ServiceCategory, ServiceItem


async def _seed_service_item(stock: int = 100) -> int:
    """Create a service category + item and return the item id."""
    from tests.conftest import test_session

    async with test_session() as db:
        cat = ServiceCategory(name="测试分类", status="active", sort_order=1)
        db.add(cat)
        await db.flush()

        item = ServiceItem(
            category_id=cat.id, name="测试服务项目", description="用于订单测试",
            price=100.00, original_price=150.00, service_type="online",
            stock=stock, sales_count=0, status="active",
        )
        db.add(item)
        await db.commit()
        return item.id


@pytest.mark.asyncio
async def test_create_order(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item()
    response = await client.post("/api/orders", json={
        "service_item_id": item_id,
        "quantity": 2,
        "payment_method": "wechat",
        "points_deduction": 0,
        "address": "北京市朝阳区",
        "notes": "尽快发货",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["service_item_id"] == item_id
    assert data["quantity"] == 2
    assert data["total_amount"] == 200.0
    assert data["order_status"] == "pending"
    assert data["payment_status"] == "pending"
    assert data["order_no"].startswith("ORD")
    assert data["address"] == "北京市朝阳区"


@pytest.mark.asyncio
async def test_create_order_insufficient_stock(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item(stock=1)
    response = await client.post("/api/orders", json={
        "service_item_id": item_id,
        "quantity": 5,
    }, headers=auth_headers)
    assert response.status_code == 400
    assert "库存不足" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_order_invalid_item(client: AsyncClient, auth_headers):
    response = await client.post("/api/orders", json={
        "service_item_id": 99999,
        "quantity": 1,
    }, headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_orders(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item()
    await client.post("/api/orders", json={
        "service_item_id": item_id, "quantity": 1,
    }, headers=auth_headers)
    await client.post("/api/orders", json={
        "service_item_id": item_id, "quantity": 1,
    }, headers=auth_headers)

    response = await client.get("/api/orders", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_orders_filter_status(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item()
    await client.post("/api/orders", json={
        "service_item_id": item_id, "quantity": 1,
    }, headers=auth_headers)

    response = await client.get(
        "/api/orders", params={"order_status": "pending"}, headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await client.get(
        "/api/orders", params={"order_status": "completed"}, headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_order_detail(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item()
    create_resp = await client.post("/api/orders", json={
        "service_item_id": item_id, "quantity": 1,
    }, headers=auth_headers)
    order_id = create_resp.json()["id"]

    response = await client.get(f"/api/orders/{order_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order_id
    assert data["service_item_id"] == item_id


@pytest.mark.asyncio
async def test_get_order_not_found(client: AsyncClient, auth_headers):
    response = await client.get("/api/orders/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_order(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item()
    create_resp = await client.post("/api/orders", json={
        "service_item_id": item_id, "quantity": 1,
    }, headers=auth_headers)
    order_id = create_resp.json()["id"]

    response = await client.put(f"/api/orders/{order_id}/cancel", headers=auth_headers)
    assert response.status_code == 200
    assert "取消" in response.json()["message"]

    detail_resp = await client.get(f"/api/orders/{order_id}", headers=auth_headers)
    assert detail_resp.json()["order_status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_already_cancelled(client: AsyncClient, auth_headers):
    item_id = await _seed_service_item()
    create_resp = await client.post("/api/orders", json={
        "service_item_id": item_id, "quantity": 1,
    }, headers=auth_headers)
    order_id = create_resp.json()["id"]

    await client.put(f"/api/orders/{order_id}/cancel", headers=auth_headers)
    response = await client.put(f"/api/orders/{order_id}/cancel", headers=auth_headers)
    assert response.status_code == 400
    assert "无法取消" in response.json()["detail"]


@pytest.mark.asyncio
async def test_unauthorized_order(client: AsyncClient):
    response = await client.post("/api/orders", json={
        "service_item_id": 1, "quantity": 1,
    })
    assert response.status_code == 401

    response = await client.get("/api/orders")
    assert response.status_code == 401


# ────────────────────────────────────────────────────────────────────────────
# 以下为 Bug 修复验证用例：H5 订单预约信息缺失
# 验证 store_name / appointment_data / appointment_time 正确返回
# ────────────────────────────────────────────────────────────────────────────

from datetime import datetime, timedelta
from app.models.models import (
    MerchantStore, Product, ProductCategory, ProductStore,
    UnifiedOrder, OrderItem, UnifiedOrderStatus, FulfillmentType,
    AppointmentMode, PurchaseAppointmentMode,
)


async def _seed_unified_order_with_store(user_id: int, with_store: bool = True, with_appointment: bool = False):
    """Create a unified order optionally bound to a store and with appointment info."""
    from tests.conftest import test_session

    async with test_session() as db:
        store = None
        if with_store:
            store = MerchantStore(
                store_name="测试门店A",
                store_code=f"STORE_{datetime.utcnow().timestamp()}",
                status="active",
            )
            db.add(store)
            await db.flush()

        cat = ProductCategory(name="测试分类", sort_order=1, status="active")
        db.add(cat)
        await db.flush()

        product = Product(
            name="预约测试商品",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=88.00,
            stock=100,
            sales_count=0,
            status="active",
            appointment_mode=AppointmentMode.date if with_appointment else AppointmentMode.none,
            purchase_appointment_mode=(
                PurchaseAppointmentMode.purchase_with_appointment if with_appointment else None
            ),
            redeem_count=1,
        )
        db.add(product)
        await db.flush()

        if with_store:
            ps = ProductStore(product_id=product.id, store_id=store.id)
            db.add(ps)
            await db.flush()

        order = UnifiedOrder(
            order_no=f"UO_TEST_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            user_id=user_id,
            total_amount=88.00,
            paid_amount=88.00,
            points_deduction=0,
            status=UnifiedOrderStatus.pending_use,
            store_id=store.id if store else None,
        )
        db.add(order)
        await db.flush()

        appt_time = datetime.utcnow() + timedelta(days=1) if with_appointment else None
        appt_data = {"time_slot": "09:00-10:00"} if with_appointment else None

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            product_price=88.00,
            quantity=1,
            subtotal=88.00,
            fulfillment_type=FulfillmentType.in_store,
            total_redeem_count=1,
            used_redeem_count=0,
            appointment_data=appt_data,
            appointment_time=appt_time,
        )
        db.add(oi)
        await db.commit()

        return order.id


async def _get_user_id_from_token(token: str) -> int:
    """Decode user id from JWT token."""
    from jose import jwt
    from app.core.config import settings
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return int(payload["sub"])


@pytest.mark.asyncio
async def test_unified_order_response_contains_store_name(client: AsyncClient, user_token, auth_headers):
    """验证订单响应中包含 store_name 字段（绑定门店时返回门店名称）"""
    user_id = await _get_user_id_from_token(user_token)
    order_id = await _seed_unified_order_with_store(user_id, with_store=True)

    response = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "store_name" in data
    assert data["store_name"] == "测试门店A"


@pytest.mark.asyncio
async def test_unified_order_store_name_none_when_no_store(client: AsyncClient, user_token, auth_headers):
    """验证无门店时 store_name 为 None"""
    user_id = await _get_user_id_from_token(user_token)
    order_id = await _seed_unified_order_with_store(user_id, with_store=False)

    response = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "store_name" in data
    assert data["store_name"] is None


@pytest.mark.asyncio
async def test_unified_order_items_contain_appointment_fields(client: AsyncClient, user_token, auth_headers):
    """验证订单项中包含 appointment_data 和 appointment_time 字段"""
    user_id = await _get_user_id_from_token(user_token)
    order_id = await _seed_unified_order_with_store(user_id, with_store=True, with_appointment=True)

    response = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) > 0
    item = data["items"][0]
    assert "appointment_data" in item
    assert "appointment_time" in item
    assert item["appointment_data"] is not None
    assert item["appointment_data"]["time_slot"] == "09:00-10:00"
    assert item["appointment_time"] is not None


@pytest.mark.asyncio
async def test_unified_order_items_appointment_null_when_not_set(client: AsyncClient, user_token, auth_headers):
    """验证无预约信息时 appointment_data 和 appointment_time 为 None"""
    user_id = await _get_user_id_from_token(user_token)
    order_id = await _seed_unified_order_with_store(user_id, with_store=False, with_appointment=False)

    response = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) > 0
    item = data["items"][0]
    assert "appointment_data" in item
    assert "appointment_time" in item
    assert item["appointment_data"] is None
    assert item["appointment_time"] is None
