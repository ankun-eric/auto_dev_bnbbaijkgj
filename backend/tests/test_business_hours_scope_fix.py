"""[2026-05-03 营业时间/营业范围保存 Bug 修复方案] 自动化测试

覆盖：
T01: 管理后台新建门店，营业时间 / 营业范围一并保存，重开数据正确
T02: 管理后台编辑门店，仅改营业时间 → 保存成功，回读正确
T03: 管理后台编辑门店，仅改营业范围 → 保存成功，回读正确
T04: 管理后台编辑门店，结束 ≤ 开始时间 → 后端返回 400
T05: 管理后台新建门店，营业时间留空 → 后端返回 400
T06: 营业时间非 30 分钟整点 → 后端返回 400
T07: 营业时间超出 07:00–22:00 范围 → 后端返回 400
T08: 商家 H5 店铺设置：可保存 business_start/business_end + business_scope
T09: 营业时间修改后，存量预约扫描返回 affected_appointments
T10: 商家后台 H5 GET /api/merchant/shop/info 返回 business_start/business_end/business_scope
T11: 列表接口 /api/admin/merchant/stores 返回 business_start/business_end/business_scope
T12: business-scope 兼容路由仍可工作但返回 deprecated=True
"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import (
    AccountIdentity,
    AppointmentMode,
    FulfillmentType,
    IdentityType,
    MerchantCategory,
    MerchantMemberRole,
    MerchantProfile,
    MerchantStore,
    MerchantStoreMembership,
    OrderItem,
    Product,
    ProductCategory,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from app.core.security import get_password_hash


@pytest_asyncio.fixture
async def cat_id():
    async with test_session() as session:
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat.id


@pytest_asyncio.fixture
async def product_cat_ids():
    """构造两个产品分类，用于测试 business_scope。"""
    async with test_session() as session:
        c1 = ProductCategory(name="健康检查", level=1, sort_order=1, status="active")
        c2 = ProductCategory(name="中医理疗", level=1, sort_order=2, status="active")
        session.add_all([c1, c2])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)
        return [c1.id, c2.id]


@pytest_asyncio.fixture
async def boss_token(client: AsyncClient, cat_id):
    """创建一个老板账号 + 主门店 + identity 绑定。"""
    async with test_session() as session:
        u = User(
            phone="13900008888",
            password_hash=get_password_hash("boss123"),
            nickname="老板",
            role=UserRole.merchant,
            status="active",
        )
        session.add(u)
        await session.flush()
        store = MerchantStore(
            store_name="老板的门店",
            store_code="MD90001",
            category_id=cat_id,
            status="active",
            lat=23.0,
            lng=113.0,
            slot_capacity=10,
            business_start="09:00",
            business_end="22:00",
        )
        session.add(store)
        await session.flush()
        ms = MerchantStoreMembership(
            user_id=u.id,
            store_id=store.id,
            member_role=MerchantMemberRole.owner,
            role_code="boss",
            status="active",
        )
        session.add(ms)
        ai = AccountIdentity(
            user_id=u.id,
            identity_type=IdentityType.merchant_owner,
            status="active",
        )
        session.add(ai)
        prof = MerchantProfile(user_id=u.id, nickname="老板")
        session.add(prof)
        await session.commit()

    res = await client.post("/api/auth/login", json={"phone": "13900008888", "password": "boss123"})
    return res.json()["access_token"], None


@pytest_asyncio.fixture
async def boss_headers(boss_token):
    token, _ = boss_token
    return {"Authorization": f"Bearer {token}"}


# ─────── T01：新建门店时一并保存营业时间 + 营业范围 ───────


@pytest.mark.asyncio
async def test_create_store_saves_business_hours_and_scope(
    client: AsyncClient, admin_headers, cat_id, product_cat_ids
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T01 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
            "business_scope": product_cat_ids,
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    sid = res.json()["id"]

    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    body = detail.json()
    assert body["business_start"] == "09:00"
    assert body["business_end"] == "22:00"
    assert sorted(body["business_scope"]) == sorted(product_cat_ids)


# ─────── T02：仅修改营业时间 ───────


@pytest.mark.asyncio
async def test_update_only_business_hours(
    client: AsyncClient, admin_headers, cat_id
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T02 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    sid = res.json()["id"]

    upd = await client.put(
        f"/api/admin/merchant/stores/{sid}",
        json={"business_start": "10:00", "business_end": "20:30"},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    body = (await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)).json()
    assert body["business_start"] == "10:00"
    assert body["business_end"] == "20:30"


# ─────── T03：仅修改营业范围 ───────


@pytest.mark.asyncio
async def test_update_only_business_scope(
    client: AsyncClient, admin_headers, cat_id, product_cat_ids
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T03 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    sid = res.json()["id"]

    upd = await client.put(
        f"/api/admin/merchant/stores/{sid}",
        json={"business_scope": product_cat_ids},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    body = (await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)).json()
    assert sorted(body["business_scope"]) == sorted(product_cat_ids)

    # 清空营业范围
    upd2 = await client.put(
        f"/api/admin/merchant/stores/{sid}",
        json={"business_scope": []},
        headers=admin_headers,
    )
    assert upd2.status_code == 200
    body2 = (await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)).json()
    assert body2["business_scope"] == []


# ─────── T04：开始 >= 结束 后端拦截 ───────


@pytest.mark.asyncio
async def test_business_hours_end_must_be_later_than_start(
    client: AsyncClient, admin_headers, cat_id
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T04 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "12:00",
            "business_end": "12:00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 400


# ─────── T05：新建门店营业时间一端缺失 → 400 ───────


@pytest.mark.asyncio
async def test_business_hours_required_when_partial(
    client: AsyncClient, admin_headers, cat_id
):
    # 仅传开始不传结束 → 400
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T05 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_business_hours_default_when_not_provided(
    client: AsyncClient, admin_headers, cat_id
):
    # 完全不传 → 兼容默认 09:00-22:00（避免老前端打挂）
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T05B 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    sid = res.json()["id"]
    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    body = detail.json()
    assert body["business_start"] == "09:00"
    assert body["business_end"] == "22:00"


# ─────── T06：非 30 分钟整点 → 400 ───────


@pytest.mark.asyncio
async def test_business_hours_must_be_30min_grid(
    client: AsyncClient, admin_headers, cat_id
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T06 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:15",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 400


# ─────── T07：超出 07:00–22:00 → 400 ───────


@pytest.mark.asyncio
async def test_business_hours_must_be_within_7_to_22(
    client: AsyncClient, admin_headers, cat_id
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T07 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "06:00",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 400


# ─────── T08：商家 H5 店铺设置可保存 start/end/scope ───────


@pytest.mark.asyncio
async def test_merchant_h5_shop_info_save_business_fields(
    client: AsyncClient, boss_headers, product_cat_ids
):
    upd = await client.put(
        "/api/merchant/shop/info",
        json={
            "business_start": "08:00",
            "business_end": "21:30",
            "business_scope": product_cat_ids,
        },
        headers=boss_headers,
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["business_start"] == "08:00"
    assert body["business_end"] == "21:30"
    assert sorted(body["business_scope"]) == sorted(product_cat_ids)
    # business_hours 兼容字段同步（由 start+end 拼接）
    assert body["business_hours"] == "08:00 - 21:30"


# ─────── T09：affected_appointments 扫描 ───────


@pytest.mark.asyncio
async def test_update_business_hours_returns_affected_appointments(
    client: AsyncClient, admin_headers, cat_id
):
    """门店原营业 09:00–22:00，存在 1 单预约时段在 18:00-19:00；
    修改营业为 09:00–17:00，affected_appointments 应 ≥ 1。"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T09 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    sid = res.json()["id"]

    # 构造一个未核销订单，含预约时段 18:00-19:00
    async with test_session() as session:
        u = User(
            phone="13911112222",
            password_hash=get_password_hash("u123"),
            nickname="预约用户",
            role=UserRole.user,
            status="active",
        )
        session.add(u)
        await session.flush()
        order = UnifiedOrder(
            order_no="TESTO9-0001",
            user_id=u.id,
            total_amount=100,
            status=UnifiedOrderStatus.pending_use,
            store_id=sid,
        )
        session.add(order)
        await session.flush()
        prod = Product(
            name="预约商品",
            sale_price=100,
            stock=10,
            fulfillment_type=FulfillmentType.in_store,
            status="active",
        )
        session.add(prod)
        await session.flush()
        item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name="预约商品",
            product_price=100,
            quantity=1,
            subtotal=100,
            fulfillment_type=FulfillmentType.in_store,
            appointment_data={"time_slot": "18:00-19:00", "date": "2026-12-31"},
        )
        session.add(item)
        await session.commit()

    upd = await client.put(
        f"/api/admin/merchant/stores/{sid}",
        json={"business_start": "09:00", "business_end": "17:00"},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    affected = upd.json().get("affected_appointments", 0)
    assert affected >= 1


# ─────── T10：商家 H5 GET 接口字段返回 ───────


@pytest.mark.asyncio
async def test_merchant_h5_shop_info_get_returns_new_fields(
    client: AsyncClient, boss_headers
):
    res = await client.get("/api/merchant/shop/info", headers=boss_headers)
    assert res.status_code == 200
    body = res.json()
    assert "business_start" in body
    assert "business_end" in body
    assert "business_scope" in body


# ─────── T11：列表接口字段返回 ───────


@pytest.mark.asyncio
async def test_list_stores_includes_new_fields(
    client: AsyncClient, admin_headers, cat_id, product_cat_ids
):
    await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T11 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
            "business_scope": product_cat_ids,
        },
        headers=admin_headers,
    )
    res = await client.get("/api/admin/merchant/stores", headers=admin_headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert any(
        it.get("business_start") == "09:00"
        and it.get("business_end") == "22:00"
        and sorted(it.get("business_scope") or []) == sorted(product_cat_ids)
        for it in items
    )


# ─────── T12：兼容路由仍可工作 ───────


@pytest.mark.asyncio
async def test_legacy_business_scope_endpoint_still_works(
    client: AsyncClient, admin_headers, cat_id, product_cat_ids
):
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "T12 门店",
            "category_id": cat_id,
            "lat": 23.0,
            "lng": 113.0,
            "business_start": "09:00",
            "business_end": "22:00",
        },
        headers=admin_headers,
    )
    sid = res.json()["id"]
    upd = await client.put(
        f"/api/admin/stores/{sid}/business-scope",
        json={"business_scope": product_cat_ids},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    assert upd.json().get("deprecated") is True
    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    assert sorted(detail.json()["business_scope"]) == sorted(product_cat_ids)
