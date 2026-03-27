import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import ServiceCategory, ServiceItem


async def _seed_service_data(client: AsyncClient):
    """Seed service categories and items via direct DB insert through the test session."""
    from tests.conftest import test_session

    async with test_session() as db:
        cat = ServiceCategory(name="健康食品", icon="🥗", description="精选食品", sort_order=1, status="active")
        db.add(cat)
        await db.flush()

        item1 = ServiceItem(
            category_id=cat.id, name="有机蔬菜套餐", description="新鲜有机蔬菜",
            price=99.00, original_price=128.00, service_type="offline",
            stock=100, sales_count=50, status="active",
        )
        item2 = ServiceItem(
            category_id=cat.id, name="健康果汁", description="鲜榨果汁",
            price=29.00, service_type="online",
            stock=200, sales_count=120, status="active",
        )
        item3 = ServiceItem(
            category_id=cat.id, name="已下架商品", description="已停售",
            price=10.00, service_type="online",
            stock=0, sales_count=0, status="inactive",
        )
        db.add_all([item1, item2, item3])
        await db.commit()
        return cat.id, item1.id, item2.id


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient):
    await _seed_service_data(client)
    response = await client.get("/api/services/categories")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["name"] == "健康食品"
    assert data["items"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_list_categories_empty(client: AsyncClient):
    response = await client.get("/api/services/categories")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_list_items(client: AsyncClient):
    await _seed_service_data(client)
    response = await client.get("/api/services/items")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert item["status"] == "active"


@pytest.mark.asyncio
async def test_list_items_by_category(client: AsyncClient):
    cat_id, _, _ = await _seed_service_data(client)
    response = await client.get("/api/services/items", params={"category_id": cat_id})
    assert response.status_code == 200
    assert response.json()["total"] == 2


@pytest.mark.asyncio
async def test_list_items_by_keyword(client: AsyncClient):
    await _seed_service_data(client)
    response = await client.get("/api/services/items", params={"keyword": "蔬菜"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "有机蔬菜套餐"


@pytest.mark.asyncio
async def test_get_item_detail(client: AsyncClient):
    _, item_id, _ = await _seed_service_data(client)
    response = await client.get(f"/api/services/items/{item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["name"] == "有机蔬菜套餐"
    assert data["price"] == 99.0
    assert data["stock"] == 100


@pytest.mark.asyncio
async def test_item_not_found(client: AsyncClient):
    response = await client.get("/api/services/items/99999")
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]
