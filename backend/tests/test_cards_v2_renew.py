"""[卡管理 v2.0 第 4 期] 续卡 / 拆 2 单 / 省钱提示 / 可续卡列表 测试"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.models.models import (
    CardDefinition,
    CardItem,
    CardRenewStrategy,
    CardScopeType,
    CardStatus,
    CardType,
    FulfillmentType,
    Product,
    ProductCategory,
    UnifiedOrder,
    UserCard,
    UserCardStatus,
)


@pytest_asyncio.fixture
async def base_product():
    async with test_session() as s:
        c = ProductCategory(name="cat", sort_order=1)
        s.add(c)
        await s.commit()
        await s.refresh(c)
        p = Product(name="p", category_id=c.id, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("200"))
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p.id


async def _make_card(*, renew_strategy=CardRenewStrategy.add_on, total_times=10, valid_days=30, item_pid=None):
    async with test_session() as s:
        cd = CardDefinition(
            name="cd",
            card_type=CardType.times,
            scope_type=CardScopeType.platform,
            price=Decimal("100"),
            total_times=total_times,
            valid_days=valid_days,
            renew_strategy=renew_strategy,
            status=CardStatus.active,
        )
        s.add(cd)
        await s.commit()
        await s.refresh(cd)
        if item_pid:
            s.add(CardItem(card_definition_id=cd.id, product_id=item_pid))
            await s.commit()
        return cd.id


async def _purchase_and_pay(client, auth_headers, cd_id):
    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd_id}, headers=auth_headers)
    order_id = r.json()["order_id"]
    pay = await client.post(f"/api/orders/unified/{order_id}/pay-card", headers=auth_headers)
    return order_id, pay.json()["user_card_id"]


@pytest.mark.asyncio
async def test_renew_card_stack(client: AsyncClient, auth_headers, base_product):
    cd_id = await _make_card(renew_strategy=CardRenewStrategy.add_on, total_times=10, valid_days=30, item_pid=base_product)
    _, ucid = await _purchase_and_pay(client, auth_headers, cd_id)

    # 发起续卡
    r = await client.post(f"/api/cards/me/{ucid}/renew", json={}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["renew_from_user_card_id"] == ucid
    new_order_id = body["order_id"]

    # 支付续卡订单
    pr = await client.post(f"/api/orders/unified/{new_order_id}/pay-card", headers=auth_headers)
    assert pr.status_code == 200
    new_ucid = pr.json()["user_card_id"]
    assert new_ucid != ucid

    async with test_session() as s:
        old = (await s.execute(select(UserCard).where(UserCard.id == ucid))).scalar_one()
        new = (await s.execute(select(UserCard).where(UserCard.id == new_ucid))).scalar_one()
        # STACK：剩余次数累加 10 + 10 = 20
        assert new.remaining_times == 20
        assert new.renew_count == 1
        assert new.renewed_from_id == ucid
        # 老卡作废
        assert old.status == UserCardStatus.expired


@pytest.mark.asyncio
async def test_renew_card_disabled(client: AsyncClient, auth_headers, base_product):
    cd_id = await _make_card(renew_strategy=CardRenewStrategy.DISABLED, item_pid=base_product)
    # 注：DISABLED 对应不支持续卡。
    _, ucid = await _purchase_and_pay(client, auth_headers, cd_id)
    r = await client.post(f"/api/cards/me/{ucid}/renew", json={}, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_savings_tip_for_product(client: AsyncClient, base_product):
    # 卡价 100、10 次 → 单次 10 元；商品价 200 → 每次省 190，10 次省 1900
    cd_id = await _make_card(item_pid=base_product, total_times=10)
    r = await client.get(f"/api/products/{base_product}/savings-tip")
    assert r.status_code == 200
    body = r.json()
    assert body["has_card"] is True
    assert body["card_id"] == cd_id
    assert body["save_amount"] > 0


@pytest.mark.asyncio
async def test_savings_tip_no_card(client: AsyncClient):
    async with test_session() as s:
        c = ProductCategory(name="x", sort_order=1)
        s.add(c)
        await s.commit()
        await s.refresh(c)
        p = Product(name="孤立商品", category_id=c.id, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("100"))
        s.add(p)
        await s.commit()
        await s.refresh(p)
        pid = p.id
    r = await client.get(f"/api/products/{pid}/savings-tip")
    assert r.status_code == 200
    assert r.json()["has_card"] is False


@pytest.mark.asyncio
async def test_renewable_cards_list(client: AsyncClient, auth_headers, base_product):
    cd_id = await _make_card(item_pid=base_product, valid_days=3)  # 3 天有效期
    _, ucid = await _purchase_and_pay(client, auth_headers, cd_id)

    r = await client.get("/api/cards/me/renewable", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(item["user_card_id"] == ucid for item in body["items"])


@pytest.mark.asyncio
async def test_checkout_split_card_only(client: AsyncClient, auth_headers, base_product):
    cd_id = await _make_card(item_pid=base_product)
    r = await client.post("/api/orders/unified/checkout", json={
        "items": [
            {"product_type": "card", "card_definition_id": cd_id, "quantity": 1},
        ],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "split_group_id" in body
    assert len(body["order_ids"]) == 1


@pytest.mark.asyncio
async def test_checkout_split_mixed(client: AsyncClient, auth_headers, base_product):
    cd_id = await _make_card(item_pid=base_product)
    r = await client.post("/api/orders/unified/checkout", json={
        "items": [
            {"product_type": "card", "card_definition_id": cd_id, "quantity": 1},
            {"product_type": "physical", "product_id": base_product, "quantity": 2},
        ],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["order_ids"]) == 2

    async with test_session() as s:
        orders = (await s.execute(select(UnifiedOrder).where(UnifiedOrder.id.in_(body["order_ids"])))).scalars().all()
        types = sorted([o.product_type for o in orders])
        assert types == ["card", "physical"]
        groups = list({o.split_group_id for o in orders})
        assert len(groups) == 1
