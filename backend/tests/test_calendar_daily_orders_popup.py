"""[预约日历当日订单弹窗 PRD v1.0] 自动化测试

覆盖范围：
- F-04 + F-15：返回结构正确（date / total / by_status / orders[]）+ 排序规则
  （待核销 → 已取消 → 已退款 → 已核销，组内按预约时段升序）
- F-03：状态合并为 pending/verified/cancelled/refunded
- F-06 + BR-04：核销码严格遵守「未核销订单接口不下发核销码字段」
- F-07：已取消订单返回 cancel_time，已退款订单返回 refund_time
- F-08 + BR-07：客户手机号完整 11 位返回
- 鉴权：未登录 401 / 无门店权限 403 / 日期格式错 400
- 边界：当日 0 单时 total=0、orders=[] 但接口仍返回 200
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
    FulfillmentType,
    IdentityType,
    MerchantCategory,
    MerchantStore,
    MerchantStoreMembership,
    OrderItem,
    OrderRedemption,
    Product,
    ProductCategory,
    ProductStore,
    RefundStatusEnum,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from tests.conftest import test_session


# ────────────────── 辅助 fixture ──────────────────


async def _ensure_category() -> int:
    async with test_session() as db:
        res = await db.execute(select(MerchantCategory).where(MerchantCategory.code == "self_store"))
        cat = res.scalar_one_or_none()
        if cat:
            return cat.id
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat.id


@pytest_asyncio.fixture
async def calendar_setup(client: AsyncClient):
    """创建 1 个 owner 商家 + 1 个门店 + 1 个商品 + 5 个订单覆盖 4 类状态。

    日期统一设为 2026-05-10，5 个订单时段分别 09:00 / 11:00 / 14:00 / 15:00 / 17:00。
    其中：
      - 待核销 2 单（09:00 + 14:00）
      - 已核销 1 单（11:00, 含核销码 + redemption 记录）
      - 已取消 1 单（15:00, 含 cancelled_at + cancel_reason）
      - 已退款 1 单（17:00, 含 refund_status=refund_success）
    """
    target_date_str = "2026-05-10"

    async with test_session() as db:
        # 商家用户（owner）
        merchant_user = User(
            phone="13901010101",
            password_hash=get_password_hash("test1234"),
            nickname="日历商家",
            role=UserRole.merchant,
        )
        db.add(merchant_user)
        await db.flush()
        merchant_user_id = merchant_user.id

        db.add(AccountIdentity(
            user_id=merchant_user_id,
            identity_type=IdentityType.merchant_owner,
            status="active",
        ))

        # 客户用户（被预约的下单人）
        cust = User(
            phone="13812345678",
            password_hash=get_password_hash("test1234"),
            nickname="张小白",
            role=UserRole.user,
        )
        db.add(cust)
        await db.flush()
        cust_id = cust.id

        cat_id = await _ensure_category()
        store = MerchantStore(
            category_id=cat_id,
            store_name="测试门店",
            store_code="ST_CAL_001",
            contact_name="店长",
            contact_phone="13800000001",
            address="朝阳区 XX 门店 3 号房",
            lat=23.0, lng=113.0, status="active",
        )
        db.add(store)
        await db.flush()
        store_id = store.id

        db.add(MerchantStoreMembership(
            user_id=merchant_user_id,
            store_id=store_id,
            member_role="owner",
            status="active",
        ))

        pcat = ProductCategory(name="测试分类", sort_order=1)
        db.add(pcat)
        await db.flush()
        product = Product(
            category_id=pcat.id,
            name="小儿推拿(60min)",
            description="测试用",
            sale_price=199.00,
            original_price=299.00,
            stock=100,
            fulfillment_type=FulfillmentType.in_store,
        )
        db.add(product)
        await db.flush()
        product_id = product.id

        db.add(ProductStore(product_id=product_id, store_id=store_id))

        # 5 个订单，按 PRD 分布
        slots = [
            ("UO_CAL_PEND1", 9, "pending_use", None),       # 待核销 09:00
            ("UO_CAL_VER", 11, "completed", None),           # 已核销 11:00（含 redemption）
            ("UO_CAL_PEND2", 14, "appointed", None),         # 待核销 14:00
            ("UO_CAL_CAN", 15, "cancelled", "客户主动取消"),  # 已取消 15:00
            ("UO_CAL_REF", 17, "refunded", None),            # 已退款 17:00
        ]

        order_ids = {}
        oi_ids = {}
        base_dt = datetime(2026, 5, 10, 0, 0, 0)
        for order_no, hour, status, cancel_reason in slots:
            uo = UnifiedOrder(
                order_no=order_no,
                user_id=cust_id,
                total_amount=199.00,
                paid_amount=199.00,
                status=UnifiedOrderStatus(status),
                store_id=store_id,
                notes=f"备注-{order_no}" if hour == 9 else None,
            )
            if status == "cancelled":
                uo.cancelled_at = datetime(2026, 5, 10, 10, 15, 22)
                uo.cancel_reason = cancel_reason
            if status == "refunded":
                uo.refund_status = RefundStatusEnum.refund_success
            db.add(uo)
            await db.flush()
            order_ids[order_no] = uo.id

            oi = OrderItem(
                order_id=uo.id,
                product_id=product_id,
                product_name="小儿推拿(60min)",
                product_price=199.00,
                quantity=1,
                subtotal=199.00,
                fulfillment_type=FulfillmentType.in_store,
                appointment_time=base_dt.replace(hour=hour),
                appointment_data={"time_slot": f"{hour:02d}:00-{hour + 1:02d}:00"},
                verification_code=f"HX2026051000{hour}",
                redemption_code_status="used" if status == "completed" else "active",
            )
            db.add(oi)
            await db.flush()
            oi_ids[order_no] = oi.id

            if status == "completed":
                # 核销记录
                db.add(OrderRedemption(
                    order_item_id=oi.id,
                    redeemed_by_user_id=merchant_user_id,
                    store_id=store_id,
                    redeemed_at=datetime(2026, 5, 10, 11, 32, 11),
                ))

        await db.commit()

    # 商家登录
    login = await client.post(
        "/api/auth/login",
        json={"phone": "13901010101", "password": "test1234"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    token = body.get("access_token") or body.get("token")

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "store_id": store_id,
        "date": target_date_str,
        "order_ids": order_ids,
    }


# ────────────────── 1. 基础结构 + 字段完整 ──────────────────


@pytest.mark.asyncio
async def test_daily_orders_basic_structure(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["date"] == s["date"]
    assert data["total"] == 5
    assert "by_status" in data
    bs = data["by_status"]
    assert bs["pending"] == 2
    assert bs["verified"] == 1
    assert bs["cancelled"] == 1
    assert bs["refunded"] == 1
    assert isinstance(data["orders"], list) and len(data["orders"]) == 5

    # 每条记录应含 PRD 要求字段
    sample = data["orders"][0]
    for key in ("order_id", "order_item_id", "order_no", "time_slot",
                "customer_nickname", "customer_phone", "service_name",
                "service_location", "status"):
        assert key in sample, f"missing field {key} in {sample}"


# ────────────────── 2. 排序规则 BR-03 / F-15 ──────────────────


@pytest.mark.asyncio
async def test_daily_orders_sorting_rule(client: AsyncClient, calendar_setup):
    """排序：待核销 → 已取消 → 已退款 → 已核销，组内按预约时段升序。"""
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert r.status_code == 200
    statuses = [o["status"] for o in r.json()["orders"]]

    # 待核销 2 单 → 已取消 1 单 → 已退款 1 单 → 已核销 1 单
    assert statuses == ["pending", "pending", "cancelled", "refunded", "verified"], statuses

    # 组内时段升序：前两个 pending 应该是 09:00 早于 14:00
    orders = r.json()["orders"]
    assert orders[0]["time_slot"].startswith("09:")
    assert orders[1]["time_slot"].startswith("14:")


# ────────────────── 3. 核销码安全规则 BR-04 ──────────────────


@pytest.mark.asyncio
async def test_verify_code_only_returned_for_verified_orders(client: AsyncClient, calendar_setup):
    """核销码必须仅在 status=verified 时下发；未核销/已取消/已退款订单 verify_code 必须为 None。"""
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert r.status_code == 200
    for o in r.json()["orders"]:
        if o["status"] == "verified":
            assert o["verify_code"], f"verified 订单必须下发 verify_code: {o}"
            assert o["verify_time"], f"verified 订单必须下发 verify_time: {o}"
        else:
            assert o.get("verify_code") in (None, ""), (
                f"非 verified 订单严禁下发 verify_code: {o}"
            )


# ────────────────── 4. 已取消订单的 cancel_time / cancel_reason ──────────────────


@pytest.mark.asyncio
async def test_cancelled_order_carries_cancel_time(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    cancelled = [o for o in r.json()["orders"] if o["status"] == "cancelled"]
    assert len(cancelled) == 1
    o = cancelled[0]
    assert o["cancel_time"] is not None
    assert "客户主动取消" in (o.get("cancel_reason") or "")


# ────────────────── 5. 已退款订单的 refund_time ──────────────────


@pytest.mark.asyncio
async def test_refunded_order_carries_refund_time(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    refunded = [o for o in r.json()["orders"] if o["status"] == "refunded"]
    assert len(refunded) == 1
    o = refunded[0]
    assert o["refund_time"] is not None


# ────────────────── 6. 客户手机号完整 11 位 BR-07 ──────────────────


@pytest.mark.asyncio
async def test_customer_phone_full_11_digits(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    for o in r.json()["orders"]:
        phone = o.get("customer_phone")
        assert phone, f"商家应能看到完整手机号: {o}"
        digits = "".join(c for c in phone if c.isdigit())
        assert len(digits) == 11, f"手机号应为 11 位: {phone}"


# ────────────────── 7. 客户昵称脱敏 ──────────────────


@pytest.mark.asyncio
async def test_customer_nickname_is_masked(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    for o in r.json()["orders"]:
        nick = o.get("customer_nickname") or ""
        # 形如「张**」开头是单字符，后跟 *
        assert "**" in nick or nick == "匿名用户", f"昵称应做脱敏: {nick}"


# ────────────────── 8. 当日 0 单 ──────────────────


@pytest.mark.asyncio
async def test_daily_orders_empty_day(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": "2027-01-01", "store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["orders"] == []
    assert data["by_status"] == {"pending": 0, "verified": 0, "cancelled": 0, "refunded": 0}


# ────────────────── 9. 鉴权：未登录返回 401 ──────────────────


@pytest.mark.asyncio
async def test_daily_orders_requires_auth(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
    )
    assert r.status_code == 401


# ────────────────── 10. 鉴权：日期格式错返回 400 ──────────────────


@pytest.mark.asyncio
async def test_daily_orders_invalid_date_format(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": "2026/05/10", "store_id": s["store_id"]},
        headers=s["headers"],
    )
    assert r.status_code == 400


# ────────────────── 11. 鉴权：无门店权限返回 403 ──────────────────


@pytest.mark.asyncio
async def test_daily_orders_no_store_access(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": 99999},  # 不存在/无权限
        headers=s["headers"],
    )
    assert r.status_code == 403


# ────────────────── 12. 状态分组计数与 orders 长度匹配 ──────────────────


@pytest.mark.asyncio
async def test_status_counts_match_orders_length(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    data = r.json()
    bs = data["by_status"]
    # PRD：by_status 是 4 类合并状态的精确计数；total 应 ≥ 4 类总和（other 兜底）
    assert data["total"] == bs["pending"] + bs["verified"] + bs["cancelled"] + bs["refunded"]
    assert bs["pending"] == 2
    assert bs["verified"] == 1
    assert bs["cancelled"] == 1
    assert bs["refunded"] == 1


# ────────────────── 13. 服务地点字段不为空 ──────────────────


@pytest.mark.asyncio
async def test_service_location_present(client: AsyncClient, calendar_setup):
    s = calendar_setup
    r = await client.get(
        "/api/merchant/calendar/daily-orders",
        params={"date": s["date"], "store_id": s["store_id"]},
        headers=s["headers"],
    )
    for o in r.json()["orders"]:
        assert o.get("service_location"), f"应回传服务地点: {o}"
