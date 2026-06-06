"""[BUG-FIX-REBUY-V1 2026-05-07]「再来一单」复购入口 Bug 修复测试。

后端新增 POST /api/orders/unified/{order_id}/reorder：
- 校验商品/SKU 在售状态，过滤已下架/删除
- 返回 status: all_available / partial_filtered / all_unavailable
"""

from datetime import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FulfillmentType,
    OrderItem,
    Product,
    ProductCategory,
    ProductSku,
    ProductStatus,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from tests.conftest import test_session


async def _get_user_id_by_phone(phone: str) -> int:
    async with test_session() as db:
        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()
        return user.id if user else 0


async def _seed_category() -> int:
    async with test_session() as db:
        cat = ProductCategory(name="按摩", sort_order=0)
        db.add(cat)
        await db.flush()
        cid = cat.id
        await db.commit()
        return cid


async def _seed_product(name: str, status: ProductStatus = ProductStatus.active, with_sku: bool = False) -> tuple[int, int | None]:
    cid = await _seed_category()
    async with test_session() as db:
        p = Product(
            name=name,
            category_id=cid,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=Decimal("99.00"),
            status=status,
        )
        db.add(p)
        await db.flush()
        pid = p.id
        sid = None
        if with_sku:
            sku = ProductSku(
                product_id=pid,
                spec_name="标准",
                sale_price=Decimal("99.00"),
                stock=100,
                is_default=True,
                status=1,
            )
            db.add(sku)
            await db.flush()
            sid = sku.id
        await db.commit()
        return pid, sid


async def _seed_order(user_id: int, items: list[dict]) -> int:
    async with test_session() as db:
        order = UnifiedOrder(
            user_id=user_id,
            order_no=f"O{datetime.now().timestamp():.0f}{user_id}",
            total_amount=Decimal("99.00"),
            paid_amount=Decimal("99.00"),
            status=UnifiedOrderStatus.completed,
        )
        db.add(order)
        await db.flush()
        for it in items:
            db.add(OrderItem(
                order_id=order.id,
                product_id=it["product_id"],
                sku_id=it.get("sku_id"),
                sku_name=it.get("sku_name"),
                product_name=it["product_name"],
                product_price=Decimal("99.00"),
                quantity=it.get("quantity", 1),
                subtotal=Decimal("99.00"),
                fulfillment_type=FulfillmentType.in_store,
            ))
        await db.commit()
        return order.id


@pytest.mark.asyncio
async def test_reorder_all_available(client: AsyncClient, auth_headers):
    """case_01：原订单全部商品仍在售 → status=all_available, available_items 完整"""
    user_id = await _get_user_id_by_phone("13900000001")
    pid, _ = await _seed_product("肩颈按摩")
    oid = await _seed_order(user_id, [{"product_id": pid, "product_name": "肩颈按摩", "quantity": 2}])

    res = await client.post(f"/api/orders/unified/{oid}/reorder", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "all_available"
    assert data["total_count"] == 1
    assert data["filtered_count"] == 0
    assert len(data["available_items"]) == 1
    assert data["available_items"][0]["product_id"] == pid
    assert data["available_items"][0]["quantity"] == 2


@pytest.mark.asyncio
async def test_reorder_all_unavailable_offline(client: AsyncClient, auth_headers):
    """case_02：原订单中商品全部下架 → status=all_unavailable，available_items 为空"""
    user_id = await _get_user_id_by_phone("13900000001")
    pid, _ = await _seed_product("已下架推拿", status=ProductStatus.inactive)
    oid = await _seed_order(user_id, [{"product_id": pid, "product_name": "已下架推拿"}])

    res = await client.post(f"/api/orders/unified/{oid}/reorder", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "all_unavailable"
    assert len(data["available_items"]) == 0
    assert data["filtered_count"] == 1
    assert data["filtered_items"][0]["reason"] == "offline"


@pytest.mark.asyncio
async def test_reorder_partial_filtered(client: AsyncClient, auth_headers):
    """case_03：部分商品下架 → status=partial_filtered，过滤下架项保留在售项"""
    user_id = await _get_user_id_by_phone("13900000001")
    pid_active, _ = await _seed_product("肩颈按摩")
    pid_offline, _ = await _seed_product("足疗", status=ProductStatus.inactive)
    oid = await _seed_order(user_id, [
        {"product_id": pid_active, "product_name": "肩颈按摩"},
        {"product_id": pid_offline, "product_name": "足疗"},
    ])

    res = await client.post(f"/api/orders/unified/{oid}/reorder", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "partial_filtered"
    assert data["total_count"] == 2
    assert data["filtered_count"] == 1
    assert len(data["available_items"]) == 1
    assert data["available_items"][0]["product_id"] == pid_active


@pytest.mark.asyncio
async def test_reorder_sku_offline(client: AsyncClient, auth_headers):
    """case_04：商品在售但 SKU 已停用 → 该 item 被过滤"""
    user_id = await _get_user_id_by_phone("13900000001")
    pid, sid = await _seed_product("精油按摩", with_sku=True)
    # 把 SKU 状态改为停用
    async with test_session() as db:
        sku = (await db.execute(select(ProductSku).where(ProductSku.id == sid))).scalar_one()
        sku.status = 2
        await db.commit()
    oid = await _seed_order(user_id, [{"product_id": pid, "sku_id": sid, "sku_name": "标准", "product_name": "精油按摩"}])

    res = await client.post(f"/api/orders/unified/{oid}/reorder", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "all_unavailable"
    assert data["filtered_items"][0]["reason"] == "sku_offline"


@pytest.mark.asyncio
async def test_reorder_order_not_found(client: AsyncClient, auth_headers):
    """case_05：订单不存在 → 404"""
    res = await client.post("/api/orders/unified/999999/reorder", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reorder_unauthorized(client: AsyncClient):
    """case_06：未携带 token → 401（顾客操作鉴权强制）"""
    res = await client.post("/api/orders/unified/1/reorder")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_reorder_other_user_order(client: AsyncClient, auth_headers):
    """case_07：访问他人订单 → 404（按所有者过滤）"""
    # 先创建另一个用户的订单
    async with test_session() as db:
        other = User(phone="13900099999", nickname="别人")
        db.add(other)
        await db.flush()
        other_id = other.id
        await db.commit()
    pid, _ = await _seed_product("按摩 X")
    oid = await _seed_order(other_id, [{"product_id": pid, "product_name": "按摩 X"}])

    res = await client.post(f"/api/orders/unified/{oid}/reorder", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reorder_product_deleted(client: AsyncClient, auth_headers):
    """case_08：原订单引用的商品已被物理删除 → reason=deleted 过滤"""
    user_id = await _get_user_id_by_phone("13900000001")
    pid, _ = await _seed_product("会被删除的服务")
    oid = await _seed_order(user_id, [{"product_id": pid, "product_name": "会被删除的服务"}])
    # 删除商品
    async with test_session() as db:
        prod = (await db.execute(select(Product).where(Product.id == pid))).scalar_one()
        await db.delete(prod)
        await db.commit()

    res = await client.post(f"/api/orders/unified/{oid}/reorder", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "all_unavailable"
    assert data["filtered_items"][0]["reason"] == "deleted"
