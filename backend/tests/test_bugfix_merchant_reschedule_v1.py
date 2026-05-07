"""[BUG-FIX-MERCHANT-RESCHEDULE-V1 2026-05-07] 商家 H5 端「调整预约时间」抽屉化修复测试

针对 bug 修复方案文档要求：
1. 移除写死的"上午/下午/晚间"二次时段弹窗
2. 按订单对应商品的预约模式（date / time_slot）分支处理改约逻辑
3. 校验：终态订单不允许改约 / 过去日期拒绝 / 当日已过去时段拒绝 / time_slot 模式必传 time_slot

本测试聚焦在后端 PUT /api/merchant/orders/{order_id}/appointment-time 接口的
分支逻辑、参数校验和落库正确性。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    AppointmentMode,
    FulfillmentType,
    MerchantCategory,
    MerchantMemberRole,
    MerchantStore,
    MerchantStoreMembership,
    MerchantStorePermission,
    OrderItem,
    Product,
    ProductCategory,
    ProductStatus,
    PurchaseAppointmentMode,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from tests.conftest import test_session


# ─────────── 测试工具 ───────────


async def _ensure_default_merchant_category() -> int:
    async with test_session() as db:
        res = await db.execute(
            select(MerchantCategory).where(MerchantCategory.code == "self_store")
        )
        cat = res.scalar_one_or_none()
        if cat:
            return cat.id
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat.id


async def _create_store_via_admin(client: AsyncClient, admin_headers, store_code: str) -> int:
    cat_id = await _ensure_default_merchant_category()
    response = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": f"测试门店{store_code}",
            "store_code": store_code,
            "category_id": cat_id,
            "contact_name": "店长",
            "contact_phone": "13800009999",
            "address": "测试地址",
            "lat": 23.1234567,
            "lng": 113.4567890,
            "status": "active",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _create_merchant_user_with_store(
    client: AsyncClient,
    admin_headers,
    *,
    phone: str,
    store_id: int,
) -> str:
    """通过 admin 创建商家员工账户并绑定到 store_id，返回登录后的 access_token。"""
    create_resp = await client.post(
        "/api/admin/merchant/accounts",
        json={
            "phone": phone,
            "password": "merchant123",
            "merchant_identity_type": "staff",
            "merchant_nickname": "改约测试员工",
            "status": "active",
            "store_permissions": [
                {
                    "store_id": store_id,
                    "module_codes": ["dashboard", "verify", "records", "messages", "profile"],
                }
            ],
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200, create_resp.text

    # 通过密码登录获取 token
    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": "merchant123"},
    )
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


async def _create_product_with_mode(
    *,
    name: str,
    appointment_mode: AppointmentMode,
) -> int:
    """直接在 DB 中插入商品（绕过 admin 接口的复杂性）。"""
    async with test_session() as db:
        # 商品分类
        cat_res = await db.execute(
            select(ProductCategory).where(ProductCategory.name == "改约测试分类")
        )
        cat = cat_res.scalar_one_or_none()
        if not cat:
            cat = ProductCategory(name="改约测试分类", status="active")
            db.add(cat)
            await db.flush()
        product = Product(
            name=name,
            category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            original_price=100,
            sale_price=99,
            stock=100,
            status=ProductStatus.active,
            images=["https://example.com/test.jpg"],
            appointment_mode=appointment_mode,
            advance_days=90,
            include_today=True,
            daily_quota=50,
            purchase_appointment_mode=PurchaseAppointmentMode.purchase_with_appointment,
            allow_reschedule=True,
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product.id


async def _create_order_with_item(
    *,
    user_id: int,
    product_id: int,
    initial_appt: datetime,
) -> int:
    async with test_session() as db:
        order = UnifiedOrder(
            order_no=f"UO_TEST_{int(datetime.now().timestamp() * 1000)}",
            user_id=user_id,
            total_amount=99,
            paid_amount=99,
            status=UnifiedOrderStatus.pending_use,
        )
        db.add(order)
        await db.flush()
        item = OrderItem(
            order_id=order.id,
            product_id=product_id,
            product_name="改约测试商品",
            product_price=99,
            quantity=1,
            subtotal=99,
            fulfillment_type=FulfillmentType.in_store,
            appointment_time=initial_appt,
            appointment_data={"date": initial_appt.strftime("%Y-%m-%d"), "time_slot": "14:00-15:00"},
        )
        db.add(item)
        await db.commit()
        return order.id


async def _get_user_id(phone: str) -> int:
    async with test_session() as db:
        res = await db.execute(select(User).where(User.phone == phone))
        u = res.scalar_one_or_none()
        assert u is not None
        return u.id


def _future_date(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def _past_date(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


# ─────────── 用例 ───────────


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_date_mode_no_time_slot_required(
    client: AsyncClient, admin_headers
):
    """T01: 按日期模式 — 仅传 new_date 即可改约成功，不需要 new_time_slot。
    历史脏数据 time_slot=14:00-15:00 在落库后会被清理。
    """
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S01")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110001", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="按日期商品", appointment_mode=AppointmentMode.date
    )
    user_id = await _get_user_id("13811110001")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    new_date = _future_date(7)
    resp = await client.put(
        f"/api/merchant/orders/{order_id}/appointment-time",
        json={"new_date": new_date},
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["appointment_mode"] == "date"
    assert body["new_date"] == new_date
    assert body["new_time_slot"] is None

    # 校验：appointment_data.time_slot 已被清掉
    async with test_session() as db:
        res = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        oi = res.scalar_one()
        assert oi.appointment_time.strftime("%Y-%m-%d") == new_date
        assert isinstance(oi.appointment_data, dict)
        assert "time_slot" not in oi.appointment_data
        assert oi.appointment_data["date"] == new_date


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_time_slot_mode_requires_slot(
    client: AsyncClient, admin_headers
):
    """T02: 按时段模式 — 不传 new_time_slot 应返回 400 "请选择预约时段"。"""
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S02")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110002", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="按时段商品", appointment_mode=AppointmentMode.time_slot
    )
    user_id = await _get_user_id("13811110002")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    resp = await client.put(
        f"/api/merchant/orders/{order_id}/appointment-time",
        json={"new_date": _future_date(5)},  # 不传 new_time_slot
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "时段" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_time_slot_mode_with_full_slot_range(
    client: AsyncClient, admin_headers
):
    """T03: 按时段模式 — 传 9 段格式 "14:00-16:00" 改约成功，落库 appointment_time 取段起点 14:00。"""
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S03")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110003", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="按时段商品3", appointment_mode=AppointmentMode.time_slot
    )
    user_id = await _get_user_id("13811110003")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    new_date = _future_date(7)
    resp = await client.put(
        f"/api/merchant/orders/{order_id}/appointment-time",
        json={"new_date": new_date, "new_time_slot": "14:00-16:00"},
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["appointment_mode"] == "time_slot"
    assert body["new_time_slot"] == "14:00-16:00"

    async with test_session() as db:
        res = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        oi = res.scalar_one()
        # appointment_time 应为 new_date 的 14:00
        assert oi.appointment_time.strftime("%Y-%m-%d %H:%M") == f"{new_date} 14:00"
        # appointment_data.time_slot 应保留 9 段格式
        assert oi.appointment_data["time_slot"] == "14:00-16:00"


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_past_date_rejected(
    client: AsyncClient, admin_headers
):
    """T04: 过去日期 — 拒绝并返回 400 "所选日期已过期"。"""
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S04")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110004", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="过去日期测试商品", appointment_mode=AppointmentMode.date
    )
    user_id = await _get_user_id("13811110004")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    resp = await client.put(
        f"/api/merchant/orders/{order_id}/appointment-time",
        json={"new_date": _past_date(2)},
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "过期" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_terminal_status_rejected(
    client: AsyncClient, admin_headers
):
    """T05: 终态订单（cancelled）拒绝改约。"""
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S05")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110005", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="终态测试商品", appointment_mode=AppointmentMode.time_slot
    )
    user_id = await _get_user_id("13811110005")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    # 把订单状态置为 cancelled
    async with test_session() as db:
        res = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
        order = res.scalar_one()
        order.status = UnifiedOrderStatus.cancelled
        await db.commit()

    resp = await client.put(
        f"/api/merchant/orders/{order_id}/appointment-time",
        json={"new_date": _future_date(5), "new_time_slot": "14:00-16:00"},
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "状态" in resp.json()["detail"] or "无法改约" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_detail_returns_appointment_mode(
    client: AsyncClient, admin_headers
):
    """T06: 商家端订单详情接口必须返回 appointment_mode 字段（让前端按模式分支显示抽屉）。"""
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S06")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110006", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="详情接口商品", appointment_mode=AppointmentMode.time_slot
    )
    user_id = await _get_user_id("13811110006")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    resp = await client.get(
        f"/api/merchant/orders/{order_id}/detail",
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "appointment_mode" in body
    assert body["appointment_mode"] == "time_slot"
    assert body["product_id"] == pid


@pytest.mark.asyncio
async def test_merchant_reschedule_v1_date_mode_with_passed_slot_arg_ignored(
    client: AsyncClient, admin_headers
):
    """T07: 按日期模式 — 即使前端误传 new_time_slot，后端也忽略它，
    落库 appointment_data.time_slot 不写入；返回的 new_time_slot 为 null。
    （守护方案文档要求"按日期商品的订单可能被错误写入了上午/下午/晚间这种与该商品无关的时段值"问题）
    """
    store_id = await _create_store_via_admin(client, admin_headers, "RSV1S07")
    token = await _create_merchant_user_with_store(
        client, admin_headers, phone="13811110007", store_id=store_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    pid = await _create_product_with_mode(
        name="按日期忽略时段", appointment_mode=AppointmentMode.date
    )
    user_id = await _get_user_id("13811110007")
    order_id = await _create_order_with_item(
        user_id=user_id,
        product_id=pid,
        initial_appt=datetime.now() + timedelta(days=1),
    )

    new_date = _future_date(7)
    resp = await client.put(
        f"/api/merchant/orders/{order_id}/appointment-time",
        json={"new_date": new_date, "new_time_slot": "上午"},  # 历史错误时段值
        params={"store_id": store_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["appointment_mode"] == "date"
    assert body["new_time_slot"] is None  # 后端忽略了误传的 "上午"

    async with test_session() as db:
        res = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        oi = res.scalar_one()
        # 落库时段不应包含"上午"或类似脏数据
        assert "time_slot" not in (oi.appointment_data or {})
