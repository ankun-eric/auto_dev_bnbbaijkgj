"""[核销订单过期+改期规则优化 v1.0] 后端回归测试

覆盖 PRD 要求的 12+ 用例：
1. 商品默认 allow_reschedule=true
2. 创建商品可显式设置 allow_reschedule=false
3. 更新商品 allow_reschedule 字段
4. 错过时段 + allow_reschedule=true + count=0 → 保持 pending_use, count=1, appointment_time=NULL
5. 错过时段 + count=1 → count=2
6. 错过时段 + count=2 → count=3
7. 错过时段 + count=3 → expired
8. 错过时段 + allow_reschedule=false → expired（不论 count）
9. 改约接口（pending_use 已有预约 → 改约）count 0→1
10. 改约接口 count=3 → 400 已达改期上限
11. 待核销订单（含 count=3）申请退款 → 通过
12. 已过期订单申请退款 → 400
13. schema_sync 启动后 products / unified_orders 含新字段（创建表后字段存在）
14. /api/stores/{id}/contact 返回门店联系电话
15. 订单详情响应包含 reschedule_count / reschedule_limit / allow_reschedule 字段
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    MerchantStore,
    OrderItem,
    Product,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from app.tasks.order_status_auto_progress import _do_r2


# ────────────── helpers ──────────────


async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    r = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _create_product(
    client: AsyncClient,
    admin_headers,
    *,
    name: str = "测试服务",
    cat_name: str = "测试分类",
    allow_reschedule: bool | None = None,
) -> dict:
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": "in_store",
        "original_price": 200,
        "sale_price": 100,
        "stock": 100,
        "status": "active",
        "images": ["https://example.com/x.jpg"],
        "appointment_mode": "none",
        "purchase_appointment_mode": "purchase_with_appointment",
    }
    if allow_reschedule is not None:
        payload["allow_reschedule"] = allow_reschedule
    r = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _seed_pending_use_order(
    db_session,
    *,
    user_phone: str,
    product_id: int,
    appt_time: datetime,
    reschedule_count: int = 0,
) -> UnifiedOrder:
    rs = await db_session.execute(select(User).where(User.phone == user_phone))
    user = rs.scalar_one()
    order = UnifiedOrder(
        order_no=f"UOTST{datetime.utcnow().strftime('%H%M%S%f')}{reschedule_count}",
        user_id=user.id,
        total_amount=100,
        paid_amount=100,
        status=UnifiedOrderStatus.pending_use,
        reschedule_count=reschedule_count,
        reschedule_limit=3,
    )
    db_session.add(order)
    await db_session.flush()

    rs = await db_session.execute(select(Product).where(Product.id == product_id))
    prod = rs.scalar_one()
    item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_name=prod.name,
        product_price=prod.sale_price,
        quantity=1,
        subtotal=prod.sale_price,
        fulfillment_type=prod.fulfillment_type,
        appointment_time=appt_time,
        total_redeem_count=1,
        used_redeem_count=0,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(order)
    return order


# ────────────── 1) 商品 schema 默认值 ──────────────


@pytest.mark.asyncio
async def test_product_default_allow_reschedule_true(client, admin_headers):
    p = await _create_product(client, admin_headers, name="P-default")
    assert p.get("allow_reschedule") is True


@pytest.mark.asyncio
async def test_product_create_with_allow_reschedule_false(client, admin_headers):
    p = await _create_product(client, admin_headers, name="P-norechg", allow_reschedule=False)
    assert p.get("allow_reschedule") is False


@pytest.mark.asyncio
async def test_product_update_allow_reschedule(client, admin_headers):
    p = await _create_product(client, admin_headers, name="P-toggle")
    pid = p["id"]
    r = await client.put(
        f"/api/admin/products/{pid}",
        json={"allow_reschedule": False},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("allow_reschedule") is False
    # 再次开启
    r2 = await client.put(
        f"/api/admin/products/{pid}",
        json={"allow_reschedule": True},
        headers=admin_headers,
    )
    assert r2.status_code == 200
    assert r2.json().get("allow_reschedule") is True


# ────────────── 4-7) 错过时段：4 档改期 ──────────────


@pytest.mark.parametrize("start_count,expected_count,expected_status", [
    (0, 1, "pending_use"),
    (1, 2, "pending_use"),
    (2, 3, "pending_use"),
    (3, 3, "expired"),
])
@pytest.mark.asyncio
async def test_overdue_pending_use_with_reschedule_allowed(
    client, admin_headers, db_session, user_token,
    start_count, expected_count, expected_status,
):
    p = await _create_product(client, admin_headers, name=f"P-overdue-{start_count}")
    yesterday = datetime.utcnow() - timedelta(days=1)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=yesterday,
        reschedule_count=start_count,
    )
    # 模拟定时器扫描
    affected = await _do_r2(db_session)
    await db_session.commit()
    assert affected >= 1

    rs = await db_session.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order.id)
    )
    refreshed = rs.scalar_one()
    s = refreshed.status.value if hasattr(refreshed.status, "value") else str(refreshed.status)
    assert s == expected_status, f"start={start_count} got status={s}"
    assert int(refreshed.reschedule_count) == expected_count

    # 当保持 pending_use 时 appointment_time 应被清空
    if expected_status == "pending_use":
        rs = await db_session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = list(rs.scalars().all())
        assert all(it.appointment_time is None for it in items), "改期后预约时间应被清空"


# ────────────── 8) 不允许改期：错过即过期 ──────────────


@pytest.mark.parametrize("count", [0, 2])
@pytest.mark.asyncio
async def test_overdue_when_not_allow_reschedule(
    client, admin_headers, db_session, user_token, count,
):
    p = await _create_product(
        client, admin_headers, name=f"P-no-reschedule-{count}",
        allow_reschedule=False,
    )
    yesterday = datetime.utcnow() - timedelta(days=1)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=yesterday,
        reschedule_count=count,
    )
    affected = await _do_r2(db_session)
    await db_session.commit()
    assert affected >= 1

    rs = await db_session.execute(select(UnifiedOrder).where(UnifiedOrder.id == order.id))
    refreshed = rs.scalar_one()
    s = refreshed.status.value if hasattr(refreshed.status, "value") else str(refreshed.status)
    assert s == "expired"


# ────────────── 9-10) 改约接口：count++ / 限流 ──────────────


@pytest.mark.asyncio
async def test_modify_appointment_increments_count(
    client, admin_headers, db_session, auth_headers,
):
    p = await _create_product(client, admin_headers, name="P-modify")
    appt_today = datetime.utcnow() + timedelta(days=2)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=appt_today,
        reschedule_count=0,
    )
    new_appt = datetime.utcnow() + timedelta(days=3)
    r = await client.post(
        f"/api/orders/unified/{order.id}/appointment",
        json={"appointment_time": new_appt.isoformat()},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("reschedule_count") == 1


@pytest.mark.asyncio
async def test_modify_appointment_blocked_at_limit(
    client, admin_headers, db_session, auth_headers,
):
    p = await _create_product(client, admin_headers, name="P-modify-limit")
    appt_today = datetime.utcnow() + timedelta(days=2)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=appt_today,
        reschedule_count=3,
    )
    new_appt = datetime.utcnow() + timedelta(days=3)
    r = await client.post(
        f"/api/orders/unified/{order.id}/appointment",
        json={"appointment_time": new_appt.isoformat()},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "改期上限" in r.json().get("detail", "")


# ────────────── 11-12) 退款：待核销可退 / 已过期不可退 ──────────────


@pytest.mark.asyncio
async def test_pending_use_at_limit_can_apply_refund(
    client, admin_headers, db_session, auth_headers,
):
    p = await _create_product(client, admin_headers, name="P-refund-pu")
    appt_future = datetime.utcnow() + timedelta(days=2)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=appt_future,
        reschedule_count=3,
    )
    r = await client.post(
        f"/api/orders/unified/{order.id}/refund",
        json={"reason": "时间冲突无法到店"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_expired_order_cannot_apply_refund(
    client, admin_headers, db_session, auth_headers,
):
    p = await _create_product(
        client, admin_headers, name="P-refund-expired", allow_reschedule=False,
    )
    yesterday = datetime.utcnow() - timedelta(days=1)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=yesterday,
        reschedule_count=0,
    )
    # 触发 expire
    await _do_r2(db_session)
    await db_session.commit()
    # 现在订单是 expired，申请退款应 400
    r = await client.post(
        f"/api/orders/unified/{order.id}/refund",
        json={"reason": "想退款"},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "过期" in r.json().get("detail", "")


# ────────────── 13) Schema 字段存在 ──────────────


@pytest.mark.asyncio
async def test_schema_has_new_columns(db_session):
    """新字段存在（SQLite 测试库通过 SQLAlchemy create_all 完成；该测试同时验证 ORM 映射可写）。"""
    p = Product(
        name="schema-check",
        category_id=1,
        fulfillment_type="in_store",
        sale_price=1,
        allow_reschedule=False,
    )
    db_session.add(p)
    await db_session.flush()
    assert p.allow_reschedule is False

    rs = await db_session.execute(select(User).where(User.phone == "13900000001"))
    user = rs.scalar_one_or_none()
    if user is None:
        # 先注册一个用户（少数测试在 db_session 直接操作时无登录）
        user = User(phone="13900000099", password_hash="x", nickname="t", role="user")
        db_session.add(user)
        await db_session.flush()
    o = UnifiedOrder(
        order_no="UOTST-SCHEMA",
        user_id=user.id,
        total_amount=1,
        paid_amount=0,
        status=UnifiedOrderStatus.pending_use,
        reschedule_count=2,
        reschedule_limit=3,
    )
    db_session.add(o)
    await db_session.flush()
    assert o.reschedule_count == 2
    assert o.reschedule_limit == 3


# ────────────── 14) 联系商家接口 ──────────────


@pytest.mark.asyncio
async def test_store_contact_endpoint(client, db_session):
    store = MerchantStore(
        store_name="测试门店", store_code="SHOP-RSCH-001",
        contact_phone="13800001234", address="北京市朝阳区xx",
    )
    db_session.add(store)
    await db_session.commit()
    await db_session.refresh(store)

    r = await client.get(f"/api/stores/{store.id}/contact")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["store_id"] == store.id
    assert data["store_name"] == "测试门店"
    assert data["contact_phone"] == "13800001234"
    assert data["address"] == "北京市朝阳区xx"

    # 不存在 → 404
    r2 = await client.get("/api/stores/999999/contact")
    assert r2.status_code == 404


# ────────────── 15) 订单详情响应包含新字段 ──────────────


@pytest.mark.asyncio
async def test_order_response_includes_reschedule_fields(
    client, admin_headers, db_session, auth_headers,
):
    p = await _create_product(client, admin_headers, name="P-resp-fields")
    appt = datetime.utcnow() + timedelta(days=2)
    order = await _seed_pending_use_order(
        db_session,
        user_phone="13900000001",
        product_id=p["id"],
        appt_time=appt,
        reschedule_count=1,
    )
    r = await client.get(f"/api/orders/unified/{order.id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "reschedule_count" in data
    assert "reschedule_limit" in data
    assert "allow_reschedule" in data
    assert data["reschedule_count"] == 1
    assert data["reschedule_limit"] == 3
    assert data["allow_reschedule"] is True
    # action_buttons 始终包含 contact_store
    assert "contact_store" in data.get("action_buttons", [])
