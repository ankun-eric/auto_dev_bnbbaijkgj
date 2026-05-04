"""[2026-05-04 订单「联系商家」电话不显示 Bug 修复 v1.0] 后端回归测试。

覆盖点：
1. 订单详情响应中包含 store_id 字段，且与 DB 一致
2. 我的订单列表响应每条均含 store_id 字段
3. /api/stores/{id}/contact 当门店无 contact_phone 时降级取 owner 注册手机号
4. 当门店既无 contact_phone 也无 owner 时，contact_phone 返回 null（不报错）
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.models import (
    MerchantMemberRole,
    MerchantStore,
    MerchantStoreMembership,
    OrderItem,
    Product,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)


async def _seed_user(db_session, phone: str = "13900000001") -> User:
    rs = await db_session.execute(select(User).where(User.phone == phone))
    user = rs.scalar_one_or_none()
    if user:
        return user
    user = User(phone=phone, password_hash="x", nickname="t", role="user")
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_store_and_order(
    db_session,
    *,
    user: User,
    contact_phone: str | None = "13800001234",
) -> tuple[MerchantStore, UnifiedOrder]:
    store = MerchantStore(
        store_name="联系商家测试门店",
        store_code=f"SHOP-CONTACT-{datetime.utcnow().strftime('%H%M%S%f')}",
        contact_phone=contact_phone,
        address="北京市朝阳区联系商家路 1 号",
    )
    db_session.add(store)
    await db_session.flush()

    prod = Product(
        name="联系商家测试商品",
        category_id=1,
        fulfillment_type="in_store",
        sale_price=99,
    )
    db_session.add(prod)
    await db_session.flush()

    order = UnifiedOrder(
        order_no=f"UOCS{datetime.utcnow().strftime('%H%M%S%f')}",
        user_id=user.id,
        total_amount=99,
        paid_amount=99,
        status=UnifiedOrderStatus.pending_use,
        store_id=store.id,
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_name=prod.name,
        product_price=prod.sale_price,
        quantity=1,
        subtotal=prod.sale_price,
        fulfillment_type=prod.fulfillment_type,
        appointment_time=datetime.utcnow() + timedelta(days=2),
        total_redeem_count=1,
        used_redeem_count=0,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(order)
    return store, order


# ──────────────────────────────────────────
# 1. 订单详情响应包含 store_id 字段
# ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_order_detail_response_includes_store_id(client, db_session, auth_headers):
    user = await _seed_user(db_session, phone="13900000001")
    store, order = await _seed_store_and_order(db_session, user=user)

    r = await client.get(f"/api/orders/unified/{order.id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # 主修：响应中必须出现 store_id 字段
    assert "store_id" in data, "订单详情响应缺少 store_id 字段——会导致 H5「联系商家」弹窗失效"
    assert data["store_id"] == store.id
    # 同时保留 store_name 兜底用
    assert data.get("store_name") == store.store_name


# ──────────────────────────────────────────
# 2. 订单列表响应每条均含 store_id 字段
# ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_order_list_response_each_item_has_store_id(
    client, db_session, auth_headers,
):
    user = await _seed_user(db_session, phone="13900000001")
    store, order = await _seed_store_and_order(db_session, user=user)

    r = await client.get("/api/orders/unified", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items", [])
    assert items, "测试用户应至少有一条订单"
    target = next((it for it in items if it.get("id") == order.id), None)
    assert target is not None, f"订单 {order.id} 未出现在列表中"
    assert "store_id" in target, "订单列表响应缺少 store_id"
    assert target["store_id"] == store.id


# ──────────────────────────────────────────
# 3. /api/stores/{id}/contact 商家手机号兜底
# ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_contact_falls_back_to_owner_phone_when_store_phone_empty(
    client, db_session,
):
    owner = await _seed_user(db_session, phone="13911119999")

    store = MerchantStore(
        store_name="无电话门店",
        store_code=f"SHOP-NOPHONE-{datetime.utcnow().strftime('%H%M%S%f')}",
        contact_phone=None,
        address="测试地址",
    )
    db_session.add(store)
    await db_session.flush()

    membership = MerchantStoreMembership(
        user_id=owner.id,
        store_id=store.id,
        member_role=MerchantMemberRole.owner,
        status="active",
    )
    db_session.add(membership)
    await db_session.commit()

    r = await client.get(f"/api/stores/{store.id}/contact")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["store_id"] == store.id
    assert data["contact_phone"] == "13911119999", (
        "门店未填联系电话时，应降级取 owner 注册手机号"
    )


# ──────────────────────────────────────────
# 4. 既无门店电话又无 owner → contact_phone=null（不报错）
# ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_contact_returns_null_when_no_phone_and_no_owner(
    client, db_session,
):
    store = MerchantStore(
        store_name="孤立门店",
        store_code=f"SHOP-LONELY-{datetime.utcnow().strftime('%H%M%S%f')}",
        contact_phone=None,
        address=None,
    )
    db_session.add(store)
    await db_session.commit()

    r = await client.get(f"/api/stores/{store.id}/contact")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["store_id"] == store.id
    assert data["contact_phone"] is None
