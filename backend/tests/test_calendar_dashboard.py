"""[商家 PC 后台「预约日历」优化 PRD v1.0] 后端自动化测试

覆盖：
- KPI（今日 / 本周 / 本月，不含 cancelled）
- cells（4 字段口径 + cancelled_count + 错误日期 400）
- items（脱敏昵称、5 态 status、_SORT_GROUP 排序）
- list（分页）
- 我的视图（CRUD + 上限 10 + default 互斥 + 跨用户隔离）
- reschedule（改时间、写改约日志、跨门店 403）
- notify（写日志、返回 result + log_id）
- 内部 scan 接口（返回 scanned/sent）
- 鉴权（401 / 跨门店 403）
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.models import (
    AccountIdentity,
    BookingNotificationLog,
    FulfillmentType,
    IdentityType,
    MerchantCalendarView,
    MerchantCategory,
    MerchantStore,
    MerchantStoreMembership,
    OrderItem,
    Product,
    ProductCategory,
    ProductStore,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from tests.conftest import test_session


# ────────────────── 公共辅助 ──────────────────


async def _ensure_category(code: str = "self_store") -> int:
    async with test_session() as db:
        res = await db.execute(select(MerchantCategory).where(MerchantCategory.code == code))
        cat = res.scalar_one_or_none()
        if cat:
            return cat.id
        cat = MerchantCategory(code=code, name="自营门店", sort=0, status="active")
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat.id


async def _make_merchant(phone: str, nickname: str) -> int:
    async with test_session() as db:
        u = User(
            phone=phone,
            password_hash=get_password_hash("test1234"),
            nickname=nickname,
            role=UserRole.merchant,
        )
        db.add(u)
        await db.flush()
        uid = u.id
        db.add(AccountIdentity(
            user_id=uid,
            identity_type=IdentityType.merchant_owner,
            status="active",
        ))
        await db.commit()
    return uid


async def _make_store(merchant_uid: int, code: str, name: str) -> int:
    cat_id = await _ensure_category()
    async with test_session() as db:
        store = MerchantStore(
            category_id=cat_id,
            store_name=name,
            store_code=code,
            contact_name="店长",
            contact_phone="13800000099",
            address=f"{name}地址",
            lat=23.0, lng=113.0, status="active",
        )
        db.add(store)
        await db.flush()
        sid = store.id
        db.add(MerchantStoreMembership(
            user_id=merchant_uid,
            store_id=sid,
            member_role="owner",
            status="active",
        ))
        await db.commit()
    return sid


async def _make_product(store_id: int, name: str = "服务A") -> int:
    async with test_session() as db:
        pcat = ProductCategory(name="测试分类", sort_order=1)
        db.add(pcat)
        await db.flush()
        product = Product(
            category_id=pcat.id,
            name=name,
            description="测试用",
            sale_price=199.00,
            original_price=299.00,
            stock=100,
            fulfillment_type=FulfillmentType.in_store,
        )
        db.add(product)
        await db.flush()
        pid = product.id
        db.add(ProductStore(product_id=pid, store_id=store_id))
        await db.commit()
    return pid


async def _make_customer(phone: str = "13812345678", nickname: str = "张小白") -> int:
    async with test_session() as db:
        u = User(
            phone=phone,
            password_hash=get_password_hash("test1234"),
            nickname=nickname,
            role=UserRole.user,
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u.id


async def _make_order(
    user_id: int,
    product_id: int,
    appt_time: datetime,
    status: str = "appointed",
    order_no: str | None = None,
    paid_amount: float = 199.00,
    store_id: int | None = None,
) -> tuple[int, int]:
    async with test_session() as db:
        uo = UnifiedOrder(
            order_no=order_no or f"UO_{datetime.utcnow().timestamp() * 1000:.0f}",
            user_id=user_id,
            total_amount=paid_amount,
            paid_amount=paid_amount,
            status=UnifiedOrderStatus(status),
            store_id=store_id,
        )
        if status == "cancelled":
            uo.cancelled_at = datetime.utcnow()
        db.add(uo)
        await db.flush()
        oid = uo.id
        oi = OrderItem(
            order_id=oid,
            product_id=product_id,
            product_name="服务A",
            product_price=paid_amount,
            quantity=1,
            subtotal=paid_amount,
            fulfillment_type=FulfillmentType.in_store,
            appointment_time=appt_time,
            appointment_data={"time_slot": appt_time.strftime("%H:%M")},
            verification_code=f"VC{int(appt_time.timestamp())}",
            redemption_code_status="active",
        )
        db.add(oi)
        await db.commit()
        await db.refresh(oi)
        return oid, oi.id


@pytest_asyncio.fixture
async def setup_basic(client: AsyncClient):
    """基础 fixture：一个商家 + 一个门店 + 一个商品 + 多个订单（覆盖今日/本月/不同状态）。"""
    mid = await _make_merchant("13901010101", "日历商家A")
    sid = await _make_store(mid, "ST_DASH_001", "驾驶舱测试门店")
    pid = await _make_product(sid)
    cust = await _make_customer()

    # 锚定时间：今天的中午（避免凌晨边界），同时落在本周/本月内
    now = datetime.utcnow()
    today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)

    # 4 单覆盖 4 类状态（appointed / completed / cancelled / refunded），全部今日
    o_pend, oi_pend = await _make_order(cust, pid, today_noon.replace(hour=10), "appointed", order_no="UO_T_PEND", store_id=sid)
    o_ver, oi_ver = await _make_order(cust, pid, today_noon.replace(hour=11), "completed", order_no="UO_T_VER", store_id=sid)
    o_can, oi_can = await _make_order(cust, pid, today_noon.replace(hour=14), "cancelled", order_no="UO_T_CAN", store_id=sid)
    o_ref, oi_ref = await _make_order(cust, pid, today_noon.replace(hour=15), "refunded", order_no="UO_T_REF", store_id=sid)

    # 商家登录
    login = await client.post(
        "/api/auth/login",
        json={"phone": "13901010101", "password": "test1234"},
    )
    body = login.json()
    token = body.get("access_token") or body.get("token")
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "headers": headers,
        "merchant_id": mid,
        "store_id": sid,
        "product_id": pid,
        "customer_id": cust,
        "today_noon": today_noon,
        "orders": {
            "pending": (o_pend, oi_pend),
            "verified": (o_ver, oi_ver),
            "cancelled": (o_can, oi_can),
            "refunded": (o_ref, oi_ref),
        },
    }


@pytest_asyncio.fixture
async def other_merchant(client: AsyncClient):
    """另一个商家 + 另一个门店，用于跨用户/跨门店隔离测试。"""
    mid = await _make_merchant("13902020202", "日历商家B")
    sid = await _make_store(mid, "ST_DASH_OTHER", "其它门店")
    login = await client.post(
        "/api/auth/login",
        json={"phone": "13902020202", "password": "test1234"},
    )
    body = login.json()
    token = body.get("access_token") or body.get("token")
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "merchant_id": mid,
        "store_id": sid,
    }


# ────────────────── 1. KPI ──────────────────


@pytest.mark.asyncio
async def test_kpi_returns_three_numbers(client: AsyncClient, setup_basic):
    s = setup_basic
    r = await client.get(
        "/api/merchant/calendar/kpi",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ("today_count", "week_count", "month_count"):
        assert key in data
        assert isinstance(data[key], int) and data[key] >= 0


@pytest.mark.asyncio
async def test_kpi_excludes_cancelled(client: AsyncClient, setup_basic):
    """4 单中：pending + verified 计入；cancelled + refunded 不计入。"""
    s = setup_basic
    r = await client.get(
        "/api/merchant/calendar/kpi",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
    )
    data = r.json()
    # 今日 4 单中，2 单（pending + verified）应计入
    assert data["today_count"] == 2, data
    # 本月也至少 2 单（>= today_count）
    assert data["month_count"] >= 2


@pytest.mark.asyncio
async def test_kpi_requires_auth(client: AsyncClient, setup_basic):
    s = setup_basic
    r = await client.get(
        "/api/merchant/calendar/kpi",
        params={"store_id": s["store_id"]},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_kpi_store_isolation(client: AsyncClient, setup_basic, other_merchant):
    """B 商家用自己的 token 调 A 商家的 store_id，应被 _ensure_store_access 拒绝（403）。"""
    s = setup_basic
    other = other_merchant
    r = await client.get(
        "/api/merchant/calendar/kpi",
        params={"store_id": s["store_id"]},
        headers=other["headers"],
    )
    assert r.status_code == 403


# ────────────────── 2. cells ──────────────────


@pytest.mark.asyncio
async def test_cells_month_returns_cells_with_4_fields(client: AsyncClient, setup_basic):
    s = setup_basic
    today = s["today_noon"]
    start = today.strftime("%Y-%m-01")
    # 取月末
    if today.month == 12:
        end_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    end = end_month.strftime("%Y-%m-%d")

    r = await client.get(
        "/api/merchant/calendar/cells",
        params={
            "store_id": s["store_id"],
            "view": "month",
            "start_date": start,
            "end_date": end,
        },
        headers=s["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "cells" in data and isinstance(data["cells"], list)
    assert len(data["cells"]) >= 28
    sample = data["cells"][0]
    for key in ("date", "booking_count", "verified_count", "occupied_rate", "revenue", "cancelled_count"):
        assert key in sample, f"missing {key}"

    # 找今日 cell：应有 booking=2 / verified=1 / cancelled=1
    today_str = today.strftime("%Y-%m-%d")
    today_cell = next(c for c in data["cells"] if c["date"] == today_str)
    assert today_cell["booking_count"] == 2, today_cell
    assert today_cell["verified_count"] == 1, today_cell
    assert today_cell["cancelled_count"] == 1, today_cell
    # revenue：refunded 不计 → pending(199) + verified(199) + cancelled(199) = 597
    assert today_cell["revenue"] == pytest.approx(597.0, abs=0.01)
    # occupied_rate 0~100
    assert 0 <= today_cell["occupied_rate"] <= 100


@pytest.mark.asyncio
async def test_cells_invalid_date_format_400(client: AsyncClient, setup_basic):
    s = setup_basic
    r = await client.get(
        "/api/merchant/calendar/cells",
        params={
            "store_id": s["store_id"],
            "view": "month",
            "start_date": "2026/05/01",
            "end_date": "2026-05-31",
        },
        headers=s["headers"],
    )
    assert r.status_code == 400


# ────────────────── 3. items ──────────────────


@pytest.mark.asyncio
async def test_items_returns_card_list(client: AsyncClient, setup_basic):
    s = setup_basic
    today = s["today_noon"].strftime("%Y-%m-%d")
    r = await client.get(
        "/api/merchant/calendar/items",
        params={
            "store_id": s["store_id"],
            "start_date": today,
            "end_date": today,
        },
        headers=s["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data["items"], list) and len(data["items"]) == 4
    sample = data["items"][0]
    for key in ("order_id", "order_item_id", "customer_nickname", "status", "amount"):
        assert key in sample
    # 脱敏
    assert "**" in sample["customer_nickname"] or sample["customer_nickname"] == "匿名用户"
    # 5 态枚举
    statuses = {it["status"] for it in data["items"]}
    assert statuses.issubset({"pending", "verified", "cancelled", "refunded", "other"})


@pytest.mark.asyncio
async def test_items_sort_pending_first(client: AsyncClient, setup_basic):
    """排序：pending 在 cancelled / refunded / verified 前面（_SORT_GROUP）。"""
    s = setup_basic
    today = s["today_noon"].strftime("%Y-%m-%d")
    r = await client.get(
        "/api/merchant/calendar/items",
        params={
            "store_id": s["store_id"],
            "start_date": today,
            "end_date": today,
        },
        headers=s["headers"],
    )
    statuses = [it["status"] for it in r.json()["items"]]
    # pending → cancelled → refunded → verified
    assert statuses == ["pending", "cancelled", "refunded", "verified"], statuses


# ────────────────── 4. list 分页 ──────────────────


@pytest.mark.asyncio
async def test_list_pagination_works(client: AsyncClient, setup_basic):
    s = setup_basic
    today = s["today_noon"].strftime("%Y-%m-%d")
    r = await client.get(
        "/api/merchant/calendar/list",
        params={
            "store_id": s["store_id"],
            "start_date": today,
            "end_date": today,
            "page": 1,
            "page_size": 2,
        },
        headers=s["headers"],
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 4
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2

    r2 = await client.get(
        "/api/merchant/calendar/list",
        params={
            "store_id": s["store_id"],
            "start_date": today,
            "end_date": today,
            "page": 2,
            "page_size": 2,
        },
        headers=s["headers"],
    )
    d2 = r2.json()
    assert d2["total"] == 4
    assert len(d2["items"]) == 2


# ────────────────── 5. 我的视图 CRUD ──────────────────


@pytest.mark.asyncio
async def test_my_views_create_get_delete(client: AsyncClient, setup_basic):
    s = setup_basic
    # 创建
    r = await client.post(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"name": "我的本周", "view_type": "week", "filter_payload": {"statuses": ["pending"]}},
    )
    assert r.status_code == 200, r.text
    vid = r.json()["id"]

    # 列表
    g = await client.get(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert g.status_code == 200
    assert any(v["id"] == vid for v in g.json()["items"])

    # 删除
    d = await client.delete(
        f"/api/merchant/calendar/views/{vid}",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert d.status_code == 200
    assert d.json()["success"] is True

    # 再次列表 → 应不含
    g2 = await client.get(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert all(v["id"] != vid for v in g2.json()["items"])


@pytest.mark.asyncio
async def test_my_views_max_10_per_user(client: AsyncClient, setup_basic):
    s = setup_basic
    for i in range(10):
        r = await client.post(
            "/api/merchant/calendar/views",
            params={"store_id": s["store_id"]},
            headers=s["headers"],
            json={"name": f"V{i}", "view_type": "month"},
        )
        assert r.status_code == 200, r.text
    # 第 11 个 → 400
    r11 = await client.post(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"name": "V_OVERFLOW", "view_type": "month"},
    )
    assert r11.status_code == 400


@pytest.mark.asyncio
async def test_my_views_set_default_unsets_others(client: AsyncClient, setup_basic):
    s = setup_basic
    # 创建 A 设 default
    rA = await client.post(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"name": "A", "view_type": "month", "is_default": True},
    )
    aid = rA.json()["id"]
    assert rA.json()["is_default"] is True

    # 创建 B 设 default
    rB = await client.post(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"name": "B", "view_type": "month", "is_default": True},
    )
    assert rB.json()["is_default"] is True

    # A 应自动变 false
    g = await client.get(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
    )
    a_view = next(v for v in g.json()["items"] if v["id"] == aid)
    assert a_view["is_default"] is False


@pytest.mark.asyncio
async def test_my_views_user_isolation(client: AsyncClient, setup_basic, other_merchant):
    """A 用户视图，B 用户调 GET 看不到。"""
    s = setup_basic
    # A 用户在自己门店创建 1 个视图
    rA = await client.post(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"name": "A_PRIVATE", "view_type": "month"},
    )
    assert rA.status_code == 200
    aid = rA.json()["id"]

    # B 用户在自己门店列表（不会看到 A 的视图）
    g = await client.get(
        "/api/merchant/calendar/views",
        params={"store_id": other_merchant["store_id"]},
        headers=other_merchant["headers"],
    )
    assert g.status_code == 200
    assert all(v["id"] != aid for v in g.json()["items"])

    # B 用户尝试访问 A 的视图：跨门店 store_id 不通过；改用 A 的 store_id 又会被门店权限拦截 → 403
    bad = await client.get(
        "/api/merchant/calendar/views",
        params={"store_id": s["store_id"]},
        headers=other_merchant["headers"],
    )
    assert bad.status_code == 403


# ────────────────── 6. 改约 ──────────────────


@pytest.mark.asyncio
async def test_reschedule_updates_appointment_time(client: AsyncClient, setup_basic):
    s = setup_basic
    _, oi_id = s["orders"]["pending"]
    new_time = (s["today_noon"].replace(hour=18)).isoformat()
    r = await client.post(
        f"/api/merchant/booking/{oi_id}/reschedule",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"new_appointment_time": new_time, "notify_customer": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert data["order_item_id"] == oi_id

    # DB 校验
    async with test_session() as db:
        oi = (await db.execute(select(OrderItem).where(OrderItem.id == oi_id))).scalar_one()
        assert oi.appointment_time.strftime("%H:%M") == "18:00"


@pytest.mark.asyncio
async def test_reschedule_writes_notification_log(client: AsyncClient, setup_basic):
    s = setup_basic
    _, oi_id = s["orders"]["pending"]
    new_time = (s["today_noon"].replace(hour=19)).isoformat()
    r = await client.post(
        f"/api/merchant/booking/{oi_id}/reschedule",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"new_appointment_time": new_time, "notify_customer": True},
    )
    assert r.status_code == 200, r.text

    async with test_session() as db:
        rows = (await db.execute(
            select(BookingNotificationLog).where(
                BookingNotificationLog.order_item_id == oi_id,
                BookingNotificationLog.scene == "rescheduled",
            )
        )).scalars().all()
        assert len(rows) >= 1


@pytest.mark.asyncio
async def test_reschedule_other_store_403(client: AsyncClient, setup_basic, other_merchant):
    s = setup_basic
    _, oi_id = s["orders"]["pending"]
    new_time = (s["today_noon"].replace(hour=20)).isoformat()
    # B 商家用自己 token 改 A 商家的订单 → 先校验 store_id（B 自己的 store），但订单不属于 B → 403
    r = await client.post(
        f"/api/merchant/booking/{oi_id}/reschedule",
        params={"store_id": other_merchant["store_id"]},
        headers=other_merchant["headers"],
        json={"new_appointment_time": new_time, "notify_customer": False},
    )
    assert r.status_code in (403, 404)


# ────────────────── 7. 联系顾客 ──────────────────


@pytest.mark.asyncio
async def test_notify_writes_log_returns_result(client: AsyncClient, setup_basic):
    s = setup_basic
    _, oi_id = s["orders"]["pending"]
    r = await client.post(
        f"/api/merchant/booking/{oi_id}/notify",
        params={"store_id": s["store_id"]},
        headers=s["headers"],
        json={"scene": "contact_customer"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "result" in data
    assert "log_id" in data and isinstance(data["log_id"], int)

    async with test_session() as db:
        log = (await db.execute(
            select(BookingNotificationLog).where(
                BookingNotificationLog.id == data["log_id"]
            )
        )).scalar_one_or_none()
        assert log is not None
        assert log.order_item_id == oi_id


# ────────────────── 8. 内部 scan ──────────────────


@pytest.mark.asyncio
async def test_internal_notify_scan_returns_count(client: AsyncClient, setup_basic):
    s = setup_basic
    r = await client.post(
        "/api/merchant/internal/calendar/notify-scan",
        params={"hours_before": 24},
        headers=s["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "scanned" in data and "sent" in data
    assert isinstance(data["scanned"], int)
    assert isinstance(data["sent"], int)
