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
