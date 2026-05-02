"""[2026-05-02 卡功能 PRD v1.1 第 1 期] 后端骨架自动化测试

覆盖：
1. Admin 创建/编辑/上下架/删除卡的全 CRUD 流程
2. 创建时校验：次卡必填 total_times、商家专属卡必填 owner_merchant_id
3. C 端卡列表（仅 active）/ 卡详情（404 已下架）
4. C 端商品的可用卡推荐（卡内项目包含本商品）
5. C 端我的-卡包查询：默认全部 / 按 status 过滤 / 过期懒迁移
6. 上架前必须先绑定项目
"""
from __future__ import annotations

from datetime import datetime, timedelta

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
    UserCard,
    UserCardStatus,
)


@pytest_asyncio.fixture
async def category_id():
    async with test_session() as session:
        cat = ProductCategory(name="健康检测", sort_order=1)
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat.id


@pytest_asyncio.fixture
async def two_products(category_id: int):
    async with test_session() as session:
        p1 = Product(
            name="经络疏通",
            category_id=category_id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=200,
            images=["https://cdn.example.com/p1.png"],
        )
        p2 = Product(
            name="艾灸理疗",
            category_id=category_id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=300,
            images=None,
        )
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)
        await session.refresh(p2)
        return p1.id, p2.id


# ─────────────── Admin CRUD ───────────────


@pytest.mark.asyncio
async def test_admin_create_times_card_ok(client: AsyncClient, admin_headers, two_products):
    p1, p2 = two_products
    payload = {
        "name": "美业 10 次卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 999.00,
        "original_price": 2000.00,
        "total_times": 10,
        "valid_days": 365,
        "store_scope": {"type": "all"},
        "renew_strategy": "add_on",
        "item_product_ids": [p1, p2],
        "description": "10 次美业服务次卡",
    }
    r = await client.post("/api/admin/cards", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "draft"
    assert data["card_type"] == "times"
    assert data["scope_type"] == "platform"
    assert data["total_times"] == 10
    assert len(data["items"]) == 2
    assert {i["product_id"] for i in data["items"]} == {p1, p2}


@pytest.mark.asyncio
async def test_admin_create_times_card_missing_total_times_422(client: AsyncClient, admin_headers, two_products):
    p1, _ = two_products
    payload = {
        "name": "无次数次卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 100,
        "valid_days": 30,
        "item_product_ids": [p1],
    }
    r = await client.post("/api/admin/cards", json=payload, headers=admin_headers)
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_admin_create_merchant_scope_without_owner_422(client: AsyncClient, admin_headers, two_products):
    p1, _ = two_products
    payload = {
        "name": "商家专属卡缺商家ID",
        "card_type": "times",
        "scope_type": "merchant",
        "price": 100,
        "total_times": 5,
        "valid_days": 30,
        "item_product_ids": [p1],
    }
    r = await client.post("/api/admin/cards", json=payload, headers=admin_headers)
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_admin_create_period_card_ok(client: AsyncClient, admin_headers, two_products):
    p1, _ = two_products
    payload = {
        "name": "30 天月卡",
        "card_type": "period",
        "scope_type": "platform",
        "price": 199,
        "valid_days": 30,
        "frequency_limit": {"scope": "day", "times": 1},
        "item_product_ids": [p1],
    }
    r = await client.post("/api/admin/cards", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["card_type"] == "period"
    assert data["frequency_limit"] == {"scope": "day", "times": 1}
    assert data["total_times"] is None


@pytest.mark.asyncio
async def test_admin_update_card_replace_items(client: AsyncClient, admin_headers, two_products):
    p1, p2 = two_products
    create = await client.post("/api/admin/cards", json={
        "name": "可编辑卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 100,
        "total_times": 5,
        "valid_days": 30,
        "item_product_ids": [p1],
    }, headers=admin_headers)
    cid = create.json()["id"]

    r = await client.put(f"/api/admin/cards/{cid}", json={
        "name": "可编辑卡-改",
        "item_product_ids": [p2],
        "valid_days": 60,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "可编辑卡-改"
    assert data["valid_days"] == 60
    assert len(data["items"]) == 1 and data["items"][0]["product_id"] == p2


@pytest.mark.asyncio
async def test_admin_activate_requires_items(client: AsyncClient, admin_headers):
    """没有项目时，上架应失败"""
    r0 = await client.post("/api/admin/cards", json={
        "name": "无项目卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 100,
        "total_times": 3,
        "valid_days": 30,
        "item_product_ids": [],
    }, headers=admin_headers)
    assert r0.status_code == 200
    cid = r0.json()["id"]
    r = await client.put(f"/api/admin/cards/{cid}/status", json={"status": "active"}, headers=admin_headers)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_admin_activate_then_deactivate(client: AsyncClient, admin_headers, two_products):
    p1, _ = two_products
    create = await client.post("/api/admin/cards", json={
        "name": "上下架卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 100,
        "total_times": 5,
        "valid_days": 30,
        "item_product_ids": [p1],
    }, headers=admin_headers)
    cid = create.json()["id"]
    r1 = await client.put(f"/api/admin/cards/{cid}/status", json={"status": "active"}, headers=admin_headers)
    assert r1.status_code == 200 and r1.json()["status"] == "active"
    r2 = await client.put(f"/api/admin/cards/{cid}/status", json={"status": "inactive"}, headers=admin_headers)
    assert r2.status_code == 200 and r2.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_admin_delete_only_draft(client: AsyncClient, admin_headers, two_products):
    p1, _ = two_products
    create = await client.post("/api/admin/cards", json={
        "name": "可删除草稿卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 50,
        "total_times": 2,
        "valid_days": 7,
        "item_product_ids": [p1],
    }, headers=admin_headers)
    cid = create.json()["id"]
    # 草稿可删
    r = await client.delete(f"/api/admin/cards/{cid}", headers=admin_headers)
    assert r.status_code == 200

    # 已上架不可删
    create2 = await client.post("/api/admin/cards", json={
        "name": "上架后不可删",
        "card_type": "times",
        "scope_type": "platform",
        "price": 50,
        "total_times": 2,
        "valid_days": 7,
        "item_product_ids": [p1],
    }, headers=admin_headers)
    cid2 = create2.json()["id"]
    await client.put(f"/api/admin/cards/{cid2}/status", json={"status": "active"}, headers=admin_headers)
    r2 = await client.delete(f"/api/admin/cards/{cid2}", headers=admin_headers)
    assert r2.status_code == 400


# ─────────────── 权限校验 ───────────────


@pytest.mark.asyncio
async def test_user_cannot_call_admin_card_create(client: AsyncClient, auth_headers, two_products):
    p1, _ = two_products
    r = await client.post("/api/admin/cards", json={
        "name": "用户偷创卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 1, "total_times": 1, "valid_days": 1,
        "item_product_ids": [p1],
    }, headers=auth_headers)
    assert r.status_code == 403


# ─────────────── C 端卡列表/详情 ───────────────


@pytest_asyncio.fixture
async def active_card_with_two_items(two_products):
    p1, p2 = two_products
    async with test_session() as session:
        card = CardDefinition(
            name="C 端可见 10 次卡",
            card_type=CardType.times,
            scope_type=CardScopeType.platform,
            price=999,
            original_price=2000,
            total_times=10,
            valid_days=180,
            store_scope={"type": "all"},
            status=CardStatus.active,
        )
        session.add(card)
        await session.flush()
        session.add(CardItem(card_definition_id=card.id, product_id=p1))
        session.add(CardItem(card_definition_id=card.id, product_id=p2))
        await session.commit()
        await session.refresh(card)
        return card.id, p1, p2


@pytest.mark.asyncio
async def test_user_list_active_cards(client: AsyncClient, active_card_with_two_items):
    cid, _, _ = active_card_with_two_items
    r = await client.get("/api/cards")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(it["id"] == cid for it in data["items"])


@pytest.mark.asyncio
async def test_user_card_detail_ok(client: AsyncClient, active_card_with_two_items):
    cid, p1, p2 = active_card_with_two_items
    r = await client.get(f"/api/cards/{cid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == cid
    assert {i["product_id"] for i in data["items"]} == {p1, p2}


@pytest.mark.asyncio
async def test_user_card_detail_inactive_404(client: AsyncClient, admin_headers, two_products):
    """draft 状态卡，C 端不可见。"""
    p1, _ = two_products
    create = await client.post("/api/admin/cards", json={
        "name": "草稿卡 C 端不见",
        "card_type": "times",
        "scope_type": "platform",
        "price": 1, "total_times": 1, "valid_days": 1,
        "item_product_ids": [p1],
    }, headers=admin_headers)
    cid = create.json()["id"]
    r = await client.get(f"/api/cards/{cid}")
    assert r.status_code == 404


# ─────────────── 商品的可用卡推荐 ───────────────


@pytest.mark.asyncio
async def test_product_available_cards(client: AsyncClient, active_card_with_two_items):
    cid, p1, p2 = active_card_with_two_items
    r = await client.get(f"/api/cards/by-product/{p1}")
    assert r.status_code == 200
    data = r.json()
    assert data["product_id"] == p1
    assert any(it["id"] == cid for it in data["items"])


@pytest.mark.asyncio
async def test_product_available_cards_unrelated_empty(client: AsyncClient, active_card_with_two_items, category_id):
    """与卡无关的商品应返回空列表。"""
    async with test_session() as session:
        p_other = Product(
            name="不在卡内的商品",
            category_id=category_id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=88,
        )
        session.add(p_other)
        await session.commit()
        await session.refresh(p_other)
        pid = p_other.id

    r = await client.get(f"/api/cards/by-product/{pid}")
    assert r.status_code == 200
    assert r.json()["items"] == []


# ─────────────── 我的-卡包 ───────────────


@pytest_asyncio.fixture
async def seeded_user_card(active_card_with_two_items, user_token):
    """给当前测试用户植入一张未消费的次卡 + 一张已过期的卡。"""
    cid, _, _ = active_card_with_two_items
    from app.models.models import User
    from sqlalchemy import select

    async with test_session() as session:
        # 找到 conftest 里 user_token 创建的用户
        u = (await session.execute(select(User).where(User.phone == "13900000001"))).scalar_one()
        now = datetime.utcnow()
        active = UserCard(
            card_definition_id=cid,
            user_id=u.id,
            remaining_times=10,
            valid_from=now,
            valid_to=now + timedelta(days=180),
            status=UserCardStatus.active,
        )
        # 一张过期但状态仍 active 的卡，用于验证懒迁移
        expired = UserCard(
            card_definition_id=cid,
            user_id=u.id,
            remaining_times=3,
            valid_from=now - timedelta(days=200),
            valid_to=now - timedelta(days=2),
            status=UserCardStatus.active,
        )
        session.add_all([active, expired])
        await session.commit()
        await session.refresh(active)
        await session.refresh(expired)
        return active.id, expired.id


@pytest.mark.asyncio
async def test_my_wallet_basic(client: AsyncClient, auth_headers, seeded_user_card):
    """卡包返回正确数量；过期卡懒迁移；返回三类计数。"""
    r = await client.get("/api/cards/me/wallet", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    assert data["expired_count"] == 1  # 懒迁移后过期卡计数 = 1
    assert data["unused_count"] == 1  # remaining_times==total_times 视为未使用


@pytest.mark.asyncio
async def test_my_wallet_filter_by_status(client: AsyncClient, auth_headers, seeded_user_card):
    r = await client.get("/api/cards/me/wallet?status=expired", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert all(it["status"] == "expired" for it in data["items"])


@pytest.mark.asyncio
async def test_my_wallet_unauthorized(client: AsyncClient):
    r = await client.get("/api/cards/me/wallet")
    assert r.status_code == 401
