"""[卡管理 v2.0 第 2 期] 购卡下单链路测试

覆盖：
1. 用户下单购卡（POST /api/cards/purchase）
2. 模拟支付成功 → 自动激活 user_card → sales_count + 1
3. 库存校验
4. 单用户限购校验
5. 未上架卡禁止购买
6. user_cards.bound_items_snapshot 写入
"""
from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

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
    UserCard,
    UserCardStatus,
)


@pytest_asyncio.fixture
async def category_id():
    async with test_session() as s:
        c = ProductCategory(name="测试", sort_order=1)
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return c.id


@pytest_asyncio.fixture
async def products(category_id: int):
    async with test_session() as s:
        p1 = Product(name="按摩", category_id=category_id, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("100"))
        p2 = Product(name="艾灸", category_id=category_id, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("200"))
        s.add_all([p1, p2])
        await s.commit()
        return [p1.id, p2.id]


async def _create_card(*, status="active", price=Decimal("500"), total_times=10, stock=None, per_user_limit=None, items=None):
    async with test_session() as s:
        cd = CardDefinition(
            name="测试卡",
            card_type=CardType.times,
            scope_type=CardScopeType.platform,
            price=price,
            total_times=total_times,
            valid_days=30,
            stock=stock,
            per_user_limit=per_user_limit,
            status=CardStatus(status),
        )
        s.add(cd)
        await s.commit()
        await s.refresh(cd)
        if items:
            for pid in items:
                s.add(CardItem(card_definition_id=cd.id, product_id=pid))
            await s.commit()
        return cd.id


@pytest.mark.asyncio
async def test_purchase_card_creates_pending_order(client: AsyncClient, auth_headers, products):
    cd_id = await _create_card(items=products)
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["product_type"] == "card"
    assert data["status"] == "pending_payment"
    assert data["card_definition_id"] == cd_id
    assert data["order_id"] > 0


@pytest.mark.asyncio
async def test_pay_card_order_activates_user_card(client: AsyncClient, auth_headers, products):
    cd_id = await _create_card(items=products)
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    order_id = r.json()["order_id"]

    pr = await client.post(f"/api/orders/unified/{order_id}/pay-card", headers=auth_headers)
    assert pr.status_code == 200, pr.text
    assert pr.json()["user_card_id"] > 0

    async with test_session() as s:
        ucs = (await s.execute(select(UserCard).where(UserCard.purchase_order_id == order_id))).scalars().all()
        assert len(ucs) == 1
        uc = ucs[0]
        assert uc.status == UserCardStatus.active
        assert uc.remaining_times == 10
        assert uc.bound_items_snapshot is not None
        # snapshot 至少包含 items 列表
        snap = uc.bound_items_snapshot
        assert "items" in snap
        assert len(snap["items"]) == 2

        cd = (await s.execute(select(CardDefinition).where(CardDefinition.id == cd_id))).scalar_one()
        assert cd.sales_count == 1


@pytest.mark.asyncio
async def test_purchase_card_stock_limit(client: AsyncClient, auth_headers, products):
    cd_id = await _create_card(items=products, stock=1)
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    assert r.status_code == 200
    # 第二次：库存为 0 应失败
    r2 = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    assert r2.status_code == 400
    assert "库存" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_purchase_card_per_user_limit(client: AsyncClient, auth_headers, products):
    cd_id = await _create_card(items=products, per_user_limit=1)
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    order_id = r.json()["order_id"]
    pr = await client.post(f"/api/orders/unified/{order_id}/pay-card", headers=auth_headers)
    assert pr.status_code == 200

    # 第 2 次购买应该被限购拦截
    r2 = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    assert r2.status_code == 400
    assert "限购" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_purchase_card_inactive_blocked(client: AsyncClient, auth_headers, products):
    cd_id = await _create_card(items=products, status="inactive")
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    assert r.status_code == 400
    assert "上架" in r.json()["detail"]


@pytest.mark.asyncio
async def test_purchase_card_not_found(client: AsyncClient, auth_headers):
    r = await client.post("/api/cards/purchase", json={"card_definition_id": 999999}, headers=auth_headers)
    assert r.status_code == 404
