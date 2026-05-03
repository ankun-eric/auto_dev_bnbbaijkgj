"""[卡管理 v2.0 第 5 期] 销售看板 + 分享海报 测试"""
from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import (
    CardDefinition,
    CardItem,
    CardScopeType,
    CardStatus,
    CardType,
    FulfillmentType,
    Product,
    ProductCategory,
)


@pytest_asyncio.fixture
async def base_product():
    async with test_session() as s:
        c = ProductCategory(name="cat", sort_order=1)
        s.add(c)
        await s.commit()
        await s.refresh(c)
        p = Product(name="p", category_id=c.id, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("100"))
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p.id


async def _make_card(item_pid):
    async with test_session() as s:
        cd = CardDefinition(
            name="cd-dash",
            card_type=CardType.times,
            scope_type=CardScopeType.platform,
            price=Decimal("300"),
            total_times=5,
            valid_days=30,
            status=CardStatus.active,
        )
        s.add(cd)
        await s.commit()
        await s.refresh(cd)
        s.add(CardItem(card_definition_id=cd.id, product_id=item_pid))
        await s.commit()
        return cd.id


@pytest.mark.asyncio
async def test_dashboard_summary_empty(client: AsyncClient, admin_headers):
    r = await client.get("/api/admin/cards/dashboard/summary", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["sales_count"] == 0
    assert body["redemption_count"] == 0


@pytest.mark.asyncio
async def test_dashboard_summary_after_sales(client: AsyncClient, auth_headers, admin_headers, base_product):
    cd_id = await _make_card(base_product)
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    order_id = r.json()["order_id"]
    await client.post(f"/api/orders/unified/{order_id}/pay-card", headers=auth_headers)

    r2 = await client.get("/api/admin/cards/dashboard/summary", headers=admin_headers)
    assert r2.status_code == 200
    body = r2.json()
    assert body["sales_count"] == 1
    assert body["sales_amount"] > 0


@pytest.mark.asyncio
async def test_dashboard_trend(client: AsyncClient, auth_headers, admin_headers, base_product):
    cd_id = await _make_card(base_product)
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    order_id = r.json()["order_id"]
    await client.post(f"/api/orders/unified/{order_id}/pay-card", headers=auth_headers)

    rt = await client.get("/api/admin/cards/dashboard/trend?granularity=day", headers=admin_headers)
    assert rt.status_code == 200
    body = rt.json()
    assert body["granularity"] == "day"
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 1
    assert body["items"][0]["sales_count"] == 1


@pytest.mark.asyncio
async def test_share_poster(client: AsyncClient, base_product):
    cd_id = await _make_card(base_product)
    r = await client.get(f"/api/cards/{cd_id}/share-poster")
    # Pillow 已安装 → 200 PNG；未安装 → 503（兼容两种环境）
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 100


@pytest.mark.asyncio
async def test_share_poster_not_found(client: AsyncClient):
    r = await client.get("/api/cards/9999999/share-poster")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_card_usage_logs_empty(client: AsyncClient, admin_headers, base_product):
    cd_id = await _make_card(base_product)
    r = await client.get(f"/api/admin/cards/{cd_id}/usage-logs", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []
