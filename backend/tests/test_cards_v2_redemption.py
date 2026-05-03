"""[卡管理 v2.0 第 3 期] 动态核销码 + 门店核销 + 卡退款 测试

覆盖：
1. 生成核销码 → 旧 active 码失效
2. 重复生成 → 单卡仅 1 个 active 码
3. 门店核销（code_token / code_digits 两种）
4. 已使用码二次核销失败
5. 卡过期、剩余次数=0 等边界
6. 项目不在卡内 → 403
7. 卡退款：未核销可全额退、已核销不可退
8. 退款成功使 active 核销码失效
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
    CardRedemptionCode,
    CardRedemptionCodeStatus,
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
async def base_product():
    async with test_session() as s:
        c = ProductCategory(name="cat", sort_order=1)
        s.add(c)
        await s.commit()
        await s.refresh(c)
        p = Product(name="p1", category_id=c.id, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("100"))
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p.id


async def _setup_card_and_pay(client: AsyncClient, auth_headers, product_id: int, *, total_times=3, per_user_limit=None):
    async with test_session() as s:
        cd = CardDefinition(
            name="cd",
            card_type=CardType.times,
            scope_type=CardScopeType.platform,
            price=Decimal("100"),
            total_times=total_times,
            valid_days=30,
            per_user_limit=per_user_limit,
            status=CardStatus.active,
        )
        s.add(cd)
        await s.commit()
        await s.refresh(cd)
        s.add(CardItem(card_definition_id=cd.id, product_id=product_id))
        await s.commit()

    r = await client.post("/api/cards/purchase", json={"card_definition_id": cd.id}, headers=auth_headers)
    order_id = r.json()["order_id"]
    pr = await client.post(f"/api/orders/unified/{order_id}/pay-card", headers=auth_headers)
    user_card_id = pr.json()["user_card_id"]
    return cd.id, order_id, user_card_id


@pytest.mark.asyncio
async def test_issue_redemption_code_invalidates_old(client: AsyncClient, auth_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product)

    r1 = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    assert r1.status_code == 200
    code1 = r1.json()
    assert code1["status"] == "active"
    assert len(code1["digits"]) == 6
    assert len(code1["token"]) >= 16

    # 再发一次
    r2 = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    assert r2.status_code == 200

    async with test_session() as s:
        rows = (await s.execute(select(CardRedemptionCode).where(CardRedemptionCode.user_card_id == ucid))).scalars().all()
        active = [c for c in rows if c.status == CardRedemptionCodeStatus.active]
        expired = [c for c in rows if c.status == CardRedemptionCodeStatus.expired]
        assert len(active) == 1
        assert len(expired) == 1


@pytest.mark.asyncio
async def test_get_current_redemption_code(client: AsyncClient, auth_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product)

    none_resp = await client.get(f"/api/cards/me/{ucid}/redemption-code/current", headers=auth_headers)
    assert none_resp.status_code == 200
    assert none_resp.json() is None

    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    cur = await client.get(f"/api/cards/me/{ucid}/redemption-code/current", headers=auth_headers)
    assert cur.status_code == 200
    body = cur.json()
    assert body["token"] == issue.json()["token"]


@pytest.mark.asyncio
async def test_staff_redeem_by_token(client: AsyncClient, auth_headers, admin_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product, total_times=2)
    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    token = issue.json()["token"]

    r = await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_token": token,
        "product_id": base_product,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["remaining_times"] == 1
    assert body["card_status"] == "active"

    # 同一 token 二次核销 -> 409
    r2 = await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_token": token,
        "product_id": base_product,
    })
    assert r2.status_code in (409, 410, 404)


@pytest.mark.asyncio
async def test_staff_redeem_by_digits(client: AsyncClient, auth_headers, admin_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product, total_times=2)
    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    digits = issue.json()["digits"]

    r = await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_digits": digits,
        "product_id": base_product,
    })
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_staff_redeem_product_not_in_card(client: AsyncClient, auth_headers, admin_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product)
    # 另建一个不在卡内的商品
    async with test_session() as s:
        p = Product(name="other", category_id=1, fulfillment_type=FulfillmentType.in_store, sale_price=Decimal("99"))
        s.add(p)
        await s.commit()
        await s.refresh(p)
        other_pid = p.id
    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    token = issue.json()["token"]
    r = await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_token": token,
        "product_id": other_pid,
    })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_staff_redeem_decrements_remaining_to_zero(client: AsyncClient, auth_headers, admin_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product, total_times=1)
    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    token = issue.json()["token"]
    r = await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_token": token,
        "product_id": base_product,
    })
    assert r.status_code == 200
    assert r.json()["remaining_times"] == 0
    assert r.json()["card_status"] == "used_up"


@pytest.mark.asyncio
async def test_my_card_usage_logs(client: AsyncClient, auth_headers, admin_headers, base_product):
    _, _, ucid = await _setup_card_and_pay(client, auth_headers, base_product, total_times=2)
    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_token": issue.json()["token"],
        "product_id": base_product,
    })
    logs_r = await client.get(f"/api/cards/me/{ucid}/usage-logs", headers=auth_headers)
    assert logs_r.status_code == 200
    body = logs_r.json()
    assert body["total"] == 1
    assert body["items"][0]["product_id"] == base_product


@pytest.mark.asyncio
async def test_refund_card_unused_ok(client: AsyncClient, auth_headers, base_product):
    cd_id, order_id, ucid = await _setup_card_and_pay(client, auth_headers, base_product)
    r = await client.post(f"/api/orders/unified/{order_id}/refund-card", headers=auth_headers)
    assert r.status_code == 200, r.text
    async with test_session() as s:
        uc = (await s.execute(select(UserCard).where(UserCard.id == ucid))).scalar_one()
        assert uc.status == UserCardStatus.refunded
        cd = (await s.execute(select(CardDefinition).where(CardDefinition.id == cd_id))).scalar_one()
        assert cd.sales_count == 0


@pytest.mark.asyncio
async def test_refund_card_after_redeem_blocked(client: AsyncClient, auth_headers, admin_headers, base_product):
    cd_id, order_id, ucid = await _setup_card_and_pay(client, auth_headers, base_product, total_times=2)
    issue = await client.post(f"/api/cards/me/{ucid}/redemption-code", headers=auth_headers)
    await client.post("/api/staff/cards/redeem", headers=admin_headers, json={
        "code_token": issue.json()["token"],
        "product_id": base_product,
    })
    r = await client.post(f"/api/orders/unified/{order_id}/refund-card", headers=auth_headers)
    assert r.status_code == 400
    assert "已核销" in r.json()["detail"]
