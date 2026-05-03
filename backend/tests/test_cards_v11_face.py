"""[2026-05-03 卡管理 PRD v1.1 优化需求] 卡面设置后端自动化测试

覆盖：
1. 创建卡时不传卡面字段 → 默认值 ST1 / BG1 / 7 / ON_CARD
2. 创建卡时显式传入卡面字段 → 持久化 + 返回正确
3. 编辑卡时仅更新卡面字段 → 部分更新生效
4. 卡面字段非法值 → 422
5. C 端列表/详情/卡包 4 个接口都返回卡面字段
6. valid_days 默认值 365（不传时）
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
async def category_id_v11():
    async with test_session() as session:
        cat = ProductCategory(name="卡面测试类目", sort_order=1)
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat.id


@pytest_asyncio.fixture
async def two_products_v11(category_id_v11: int):
    async with test_session() as session:
        p1 = Product(
            name="按摩",
            category_id=category_id_v11,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=100,
            images=["https://cdn.example.com/x.png"],
        )
        p2 = Product(
            name="艾灸",
            category_id=category_id_v11,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=200,
        )
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)
        await session.refresh(p2)
        return p1.id, p2.id


# ─────────────── 创建卡：默认卡面字段 ───────────────


@pytest.mark.asyncio
async def test_create_card_face_defaults(client: AsyncClient, admin_headers, two_products_v11):
    p1, _ = two_products_v11
    r = await client.post("/api/admin/cards", json={
        "name": "默认卡面卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 100,
        "total_times": 5,
        # 不传 valid_days，验证默认 365
        "item_product_ids": [p1],
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["face_style"] == "ST1"
    assert data["face_bg_code"] == "BG1"
    assert data["face_show_flags"] == 7
    assert data["face_layout"] == "ON_CARD"
    assert data["valid_days"] == 365


@pytest.mark.asyncio
async def test_create_card_with_explicit_face(client: AsyncClient, admin_headers, two_products_v11):
    p1, p2 = two_products_v11
    r = await client.post("/api/admin/cards", json={
        "name": "节日喜庆朱红卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 599,
        "total_times": 12,
        "valid_days": 90,
        "item_product_ids": [p1, p2],
        "face_style": "ST3",
        "face_bg_code": "BG3",
        "face_show_flags": 15,  # SH1+SH2+SH3+SH4
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["face_style"] == "ST3"
    assert data["face_bg_code"] == "BG3"
    assert data["face_show_flags"] == 15


@pytest.mark.asyncio
async def test_create_card_invalid_face_style(client: AsyncClient, admin_headers, two_products_v11):
    p1, _ = two_products_v11
    r = await client.post("/api/admin/cards", json={
        "name": "非法风格",
        "card_type": "times",
        "scope_type": "platform",
        "price": 1, "total_times": 1, "valid_days": 1,
        "item_product_ids": [p1],
        "face_style": "ST9",
    }, headers=admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_card_invalid_bg_code(client: AsyncClient, admin_headers, two_products_v11):
    p1, _ = two_products_v11
    r = await client.post("/api/admin/cards", json={
        "name": "非法色板",
        "card_type": "times",
        "scope_type": "platform",
        "price": 1, "total_times": 1, "valid_days": 1,
        "item_product_ids": [p1],
        "face_bg_code": "BG99",
    }, headers=admin_headers)
    assert r.status_code == 422


# ─────────────── 编辑卡：仅更新卡面字段 ───────────────


@pytest.mark.asyncio
async def test_update_card_face_only(client: AsyncClient, admin_headers, two_products_v11):
    p1, _ = two_products_v11
    create = await client.post("/api/admin/cards", json={
        "name": "可改卡面卡",
        "card_type": "times",
        "scope_type": "platform",
        "price": 100, "total_times": 5, "valid_days": 365,
        "item_product_ids": [p1],
    }, headers=admin_headers)
    cid = create.json()["id"]

    r = await client.put(f"/api/admin/cards/{cid}", json={
        "face_style": "ST4",
        "face_bg_code": "BG7",
        "face_show_flags": 1,  # 只显示卡名
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["face_style"] == "ST4"
    assert data["face_bg_code"] == "BG7"
    assert data["face_show_flags"] == 1
    # 非卡面字段保持不变
    assert data["name"] == "可改卡面卡"
    assert data["total_times"] == 5


# ─────────────── C 端接口返回卡面字段 ───────────────


@pytest_asyncio.fixture
async def active_card_with_face(two_products_v11):
    p1, p2 = two_products_v11
    async with test_session() as session:
        card = CardDefinition(
            name="C 端卡面验证卡",
            card_type=CardType.times,
            scope_type=CardScopeType.platform,
            price=399,
            original_price=999,
            total_times=8,
            valid_days=180,
            store_scope={"type": "all"},
            status=CardStatus.active,
            face_style="ST2",
            face_bg_code="BG4",
            face_show_flags=15,
            face_layout="ON_CARD",
        )
        session.add(card)
        await session.flush()
        session.add(CardItem(card_definition_id=card.id, product_id=p1))
        session.add(CardItem(card_definition_id=card.id, product_id=p2))
        await session.commit()
        await session.refresh(card)
        return card.id


@pytest.mark.asyncio
async def test_c_list_returns_face_fields(client: AsyncClient, active_card_with_face):
    cid = active_card_with_face
    r = await client.get("/api/cards")
    assert r.status_code == 200
    items = r.json()["items"]
    target = next((it for it in items if it["id"] == cid), None)
    assert target is not None
    assert target["face_style"] == "ST2"
    assert target["face_bg_code"] == "BG4"
    assert target["face_show_flags"] == 15
    assert target["face_layout"] == "ON_CARD"


@pytest.mark.asyncio
async def test_c_detail_returns_face_fields(client: AsyncClient, active_card_with_face):
    cid = active_card_with_face
    r = await client.get(f"/api/cards/{cid}")
    assert r.status_code == 200
    data = r.json()
    assert data["face_style"] == "ST2"
    assert data["face_bg_code"] == "BG4"
    assert data["face_show_flags"] == 15


@pytest.mark.asyncio
async def test_my_wallet_returns_face_fields(client: AsyncClient, auth_headers, active_card_with_face):
    cid = active_card_with_face
    from app.models.models import User
    from sqlalchemy import select

    async with test_session() as session:
        u = (await session.execute(select(User).where(User.phone == "13900000001"))).scalar_one()
        now = datetime.utcnow()
        uc = UserCard(
            card_definition_id=cid,
            user_id=u.id,
            remaining_times=8,
            valid_from=now,
            valid_to=now + timedelta(days=180),
            status=UserCardStatus.active,
        )
        session.add(uc)
        await session.commit()

    r = await client.get("/api/cards/me/wallet", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    it = items[0]
    assert it["face_style"] == "ST2"
    assert it["face_bg_code"] == "BG4"
    assert it["face_show_flags"] == 15


# ─────────────── F04 商家档案搜索（lookup） ───────────────


@pytest.mark.asyncio
async def test_lookup_merchants_admin_only(client: AsyncClient, admin_headers, auth_headers):
    # admin 可访问
    r = await client.get("/api/admin/cards/_lookup/merchants", headers=admin_headers)
    assert r.status_code == 200
    assert "items" in r.json()
    # 普通用户 403
    r2 = await client.get("/api/admin/cards/_lookup/merchants", headers=auth_headers)
    assert r2.status_code == 403
