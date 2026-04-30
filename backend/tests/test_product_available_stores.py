"""Tests for GET /api/products/{product_id}/available-stores"""
from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models.models import (
    FulfillmentType,
    MerchantStore,
    Product,
    ProductCategory,
    ProductStore,
)
from tests.conftest import test_session


@pytest_asyncio.fixture
async def product_with_stores():
    """Seed: 1 product, 3 active stores (with lat/lng), 1 inactive store, all bound."""
    async with test_session() as db:
        cat = ProductCategory(name="测试分类_AS", sort_order=1, status="active")
        db.add(cat)
        await db.flush()

        product = Product(
            name="可用门店测试商品",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=99.00,
            stock=100,
            sales_count=0,
            status="active",
            redeem_count=1,
        )
        db.add(product)
        await db.flush()

        ts = datetime.utcnow().timestamp()
        # Store A: 上海人民广场 ~ (31.231706, 121.472644)
        store_a = MerchantStore(
            store_name="A 人民广场店",
            store_code=f"AS_A_{ts}",
            status="active",
            address="上海市黄浦区人民大道",
            lat=Decimal("31.231706"),
            lng=Decimal("121.472644"),
        )
        # Store B: 上海陆家嘴 ~ (31.239692, 121.499718) — 距离人民广场约 2-3 km
        store_b = MerchantStore(
            store_name="B 陆家嘴店",
            store_code=f"AS_B_{ts}",
            status="active",
            address="上海市浦东新区陆家嘴",
            lat=Decimal("31.239692"),
            lng=Decimal("121.499718"),
        )
        # Store C: 北京天安门 ~ (39.908692, 116.397477) — 距离上海 ~1100 km
        store_c = MerchantStore(
            store_name="C 天安门店",
            store_code=f"AS_C_{ts}",
            status="active",
            address="北京市东城区东长安街",
            lat=Decimal("39.908692"),
            lng=Decimal("116.397477"),
        )
        # Inactive store — 不应返回
        store_d = MerchantStore(
            store_name="D 停业门店",
            store_code=f"AS_D_{ts}",
            status="inactive",
            address="某地址",
            lat=Decimal("31.000000"),
            lng=Decimal("121.000000"),
        )
        db.add_all([store_a, store_b, store_c, store_d])
        await db.flush()

        for s in (store_a, store_b, store_c, store_d):
            db.add(ProductStore(product_id=product.id, store_id=s.id))
        await db.commit()

        return {
            "product_id": product.id,
            "store_a_id": store_a.id,
            "store_b_id": store_b.id,
            "store_c_id": store_c.id,
            "store_d_id": store_d.id,
        }


@pytest_asyncio.fixture
async def product_without_stores():
    """Seed: 1 product without any store binding."""
    async with test_session() as db:
        cat = ProductCategory(name="测试分类_AS_EMPTY", sort_order=1, status="active")
        db.add(cat)
        await db.flush()

        product = Product(
            name="无门店商品",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=10.00,
            stock=1,
            sales_count=0,
            status="active",
            redeem_count=1,
        )
        db.add(product)
        await db.commit()
        return product.id


@pytest.mark.asyncio
async def test_available_stores_with_user_location(client, product_with_stores):
    """传 lat/lng → 按 distance_km 升序，第一项 is_nearest=true，sort_by=distance，inactive 不返回"""
    pid = product_with_stores["product_id"]
    resp = await client.get(
        f"/api/products/{pid}/available-stores",
        params={"lat": 31.231700, "lng": 121.472640},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["sort_by"] == "distance"
    assert data["user_location"] == {"lat": 31.2317, "lng": 121.47264, "source": "gps"}

    stores = data["stores"]
    assert len(stores) == 3, "inactive 门店不应返回"
    names = [s["name"] for s in stores]
    assert "D 停业门店" not in names

    # 距离升序：A 最近 → B 次之 → C 最远
    assert stores[0]["name"] == "A 人民广场店"
    assert stores[1]["name"] == "B 陆家嘴店"
    assert stores[2]["name"] == "C 天安门店"

    assert stores[0]["is_nearest"] is True
    assert stores[1]["is_nearest"] is False
    assert stores[2]["is_nearest"] is False

    for i in range(len(stores) - 1):
        d1, d2 = stores[i]["distance_km"], stores[i + 1]["distance_km"]
        assert d1 is not None and d2 is not None
        assert d1 <= d2

    assert stores[0]["distance_km"] is not None and stores[0]["distance_km"] < 1.0
    assert stores[2]["distance_km"] is not None and stores[2]["distance_km"] > 500


@pytest.mark.asyncio
async def test_available_stores_without_user_location(client, product_with_stores):
    """不传 lat/lng → 按 name 升序，sort_by=name，distance_km 全为 null"""
    pid = product_with_stores["product_id"]
    resp = await client.get(f"/api/products/{pid}/available-stores")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["sort_by"] == "name"
    assert data["user_location"] is None

    stores = data["stores"]
    assert len(stores) == 3
    names = [s["name"] for s in stores]
    assert names == sorted(names)
    assert "D 停业门店" not in names

    for s in stores:
        assert s["distance_km"] is None
        assert s["is_nearest"] is False


@pytest.mark.asyncio
async def test_available_stores_only_one_coord_falls_back_to_name_sort(client, product_with_stores):
    """仅传 lat 或仅传 lng → 视为未传位置，按 name 排序"""
    pid = product_with_stores["product_id"]
    resp = await client.get(f"/api/products/{pid}/available-stores", params={"lat": 31.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["sort_by"] == "name"
    assert body["data"]["user_location"] is None


@pytest.mark.asyncio
async def test_available_stores_no_binding_returns_empty(client, product_without_stores):
    """商品无门店绑定 → stores 为空数组"""
    resp = await client.get(f"/api/products/{product_without_stores}/available-stores")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["stores"] == []
    assert body["data"]["sort_by"] == "name"


@pytest.mark.asyncio
async def test_available_stores_product_not_found(client):
    """product_id 不存在 → 404"""
    resp = await client.get("/api/products/99999999/available-stores")
    assert resp.status_code == 404
