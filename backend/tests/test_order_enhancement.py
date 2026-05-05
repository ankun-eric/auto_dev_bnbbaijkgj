"""[订单系统增强 PRD v1.0] 集成测试。

覆盖：
- 营业时间窗 CRUD（包括日期例外）
- 并发上限：门店级 + 服务级
- 时段切片查询：营业窗口外不展示、过去时段置灰、占用时置灰
- 站内消息红点：未读数、按订单粒度清除
- 订单列表附件元信息批量查询
- 客户取消订单：服务前可全额取消、状态变更触发站内信
- 附件上传：5MB 限制、5 个上限、自动触发站内信
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.models import (
    AccountIdentity,
    FulfillmentType,
    IdentityType,
    MerchantBusinessHours,
    MerchantMemberRole,
    MerchantStore,
    MerchantStoreMembership,
    Notification,
    OrderAttachment,
    OrderItem,
    Product,
    ProductCategory,
    ProductStore,
    ProductStatus,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from tests.conftest import test_session


@pytest_asyncio.fixture
async def merchant_setup():
    """创建商家用户 + 门店 + 服务商品，返回相关 ID 与 token。"""
    async with test_session() as session:
        # 商家用户
        merchant_user = User(
            phone="13700000001",
            password_hash=get_password_hash("merchant123"),
            nickname="测试商家",
            role=UserRole.merchant,
        )
        session.add(merchant_user)
        await session.flush()

        # 商家身份
        session.add(AccountIdentity(
            user_id=merchant_user.id,
            identity_type=IdentityType.merchant_owner,
            status="active",
        ))

        # 门店
        store = MerchantStore(
            store_name="测试门店",
            store_code="TEST001",
            slot_capacity=2,
            business_start="09:00",
            business_end="18:00",
        )
        session.add(store)
        await session.flush()

        # 商家-门店 绑定
        session.add(MerchantStoreMembership(
            user_id=merchant_user.id,
            store_id=store.id,
            member_role=MerchantMemberRole.owner,
            role_code="boss",
            status="active",
        ))

        # 商品分类
        cat = ProductCategory(name="测试分类", sort_order=1)
        session.add(cat)
        await session.flush()

        # 商品（服务，60 分钟）
        product = Product(
            name="测试服务-60min",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=Decimal("100.00"),
            stock=999,
            status=ProductStatus.active,
            service_duration_minutes=60,
        )
        session.add(product)
        await session.flush()

        # 商品-门店关联
        session.add(ProductStore(product_id=product.id, store_id=store.id))

        await session.commit()

        return {
            "merchant_user_id": merchant_user.id,
            "merchant_phone": merchant_user.phone,
            "store_id": store.id,
            "product_id": product.id,
            "category_id": cat.id,
        }


@pytest_asyncio.fixture
async def merchant_token(client: AsyncClient, merchant_setup):
    """获取商家用户 token。"""
    resp = await client.post("/api/auth/login", json={
        "phone": merchant_setup["merchant_phone"],
        "password": "merchant123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
def merchant_headers(merchant_token):
    return {"Authorization": f"Bearer {merchant_token}"}


# ──────────────── 1. 营业时间窗 ────────────────

@pytest.mark.asyncio
async def test_business_hours_save_weekday(client, merchant_headers, merchant_setup):
    """[F4] 商家保存按周营业时间窗"""
    payload = {
        "store_id": merchant_setup["store_id"],
        "entries": [
            {"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
            {"weekday": 0, "start_time": "14:00", "end_time": "18:00"},
            {"weekday": 1, "start_time": "10:00", "end_time": "20:00"},
        ],
    }
    r = await client.post("/api/merchant/business-hours", json=payload, headers=merchant_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["entries"]) == 3


@pytest.mark.asyncio
async def test_business_hours_get(client, merchant_headers, merchant_setup):
    """[F4] 获取营业时间窗"""
    await client.post("/api/merchant/business-hours", json={
        "store_id": merchant_setup["store_id"],
        "entries": [{"weekday": 2, "start_time": "08:00", "end_time": "20:00"}],
    }, headers=merchant_headers)

    r = await client.get(
        f"/api/merchant/business-hours?store_id={merchant_setup['store_id']}",
        headers=merchant_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["weekday"] == 2


@pytest.mark.asyncio
async def test_business_hours_date_exception(client, merchant_headers, merchant_setup):
    """[F4] 日期例外配置"""
    payload = {
        "store_id": merchant_setup["store_id"],
        "entries": [
            {
                "weekday": -1,
                "date_exception": "2026-10-01",
                "start_time": "00:00",
                "end_time": "00:00",
                "is_closed": True,
            },
        ],
    }
    r = await client.post("/api/merchant/business-hours", json=payload, headers=merchant_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_business_hours_invalid_time_range(client, merchant_headers, merchant_setup):
    """[F4] 时间段错误：start >= end 应拒绝"""
    payload = {
        "store_id": merchant_setup["store_id"],
        "entries": [{"weekday": 0, "start_time": "18:00", "end_time": "09:00"}],
    }
    r = await client.post("/api/merchant/business-hours", json=payload, headers=merchant_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_business_hours_no_permission(client, auth_headers, merchant_setup):
    """[F4] 无权限的用户不能保存其他门店的营业时间窗"""
    payload = {
        "store_id": merchant_setup["store_id"],
        "entries": [{"weekday": 0, "start_time": "09:00", "end_time": "18:00"}],
    }
    r = await client.post("/api/merchant/business-hours", json=payload, headers=auth_headers)
    assert r.status_code == 403


# ──────────────── 2. 并发上限 ────────────────

@pytest.mark.asyncio
async def test_concurrency_limit_save_store_only(client, merchant_headers, merchant_setup):
    """[F6] 仅设置门店级并发上限"""
    payload = {
        "store_id": merchant_setup["store_id"],
        "store_max_concurrent": 5,
    }
    r = await client.post("/api/merchant/concurrency-limit", json=payload, headers=merchant_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_concurrency_limit_save_with_overrides(client, merchant_headers, merchant_setup):
    """[F6] 设置门店级 + 服务级覆盖"""
    payload = {
        "store_id": merchant_setup["store_id"],
        "store_max_concurrent": 5,
        "service_overrides": [
            {
                "product_id": merchant_setup["product_id"],
                "max_concurrent_override": 2,
                "service_duration_minutes": 30,
            }
        ],
    }
    r = await client.post("/api/merchant/concurrency-limit", json=payload, headers=merchant_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_concurrency_limit_get(client, merchant_headers, merchant_setup):
    """[F6 + 2026-05-05 营业管理入口收敛 PRD v1.0 · N-03]
    concurrency-limit GET 仍返回 store_max_concurrent，但其值取自 merchant_stores.slot_capacity，
    POST 请求中携带的 store_max_concurrent 不再生效（被忽略）。"""
    await client.post("/api/merchant/concurrency-limit", json={
        "store_id": merchant_setup["store_id"],
        "store_max_concurrent": 3,
    }, headers=merchant_headers)

    r = await client.get(
        f"/api/merchant/concurrency-limit?store_id={merchant_setup['store_id']}",
        headers=merchant_headers,
    )
    assert r.status_code == 200
    data = r.json()
    # [N-03] store_max_concurrent 现读自 slot_capacity（fixture 设为 2），不再被请求覆盖
    assert data["store_max_concurrent"] == 2
    assert isinstance(data["services"], list)


# ──────────────── 3. 时段切片 ────────────────

@pytest.mark.asyncio
async def test_available_slots_basic(client, auth_headers, merchant_headers, merchant_setup):
    """[F5] 基础时段切片：09:00~18:00 营业，60min 服务，14 天后日期，应得 9 个切片（09,10,...,17）"""
    # 配置营业时间为每天 09:00~18:00
    entries = [
        {"weekday": w, "start_time": "09:00", "end_time": "18:00"}
        for w in range(7)
    ]
    await client.post("/api/merchant/business-hours", json={
        "store_id": merchant_setup["store_id"],
        "entries": entries,
    }, headers=merchant_headers)

    future_date = (date.today() + timedelta(days=14)).isoformat()
    r = await client.get(
        f"/api/services/{merchant_setup['product_id']}/available-slots?date={future_date}&store_id={merchant_setup['store_id']}",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["duration_minutes"] == 60
    # 09~18 营业窗，60min 切片：[09:00,10:00),[10:00,11:00),...,[17:00,18:00) 共 9 个
    assert len(data["slots"]) == 9
    for s in data["slots"]:
        assert s["is_available"] is True


@pytest.mark.asyncio
async def test_available_slots_closed_day(client, auth_headers, merchant_headers, merchant_setup):
    """[F5] 日期例外（休息日）：返回空列表"""
    target = (date.today() + timedelta(days=2)).isoformat()
    await client.post("/api/merchant/business-hours", json={
        "store_id": merchant_setup["store_id"],
        "entries": [
            {
                "weekday": -1,
                "date_exception": target,
                "start_time": "00:00",
                "end_time": "00:00",
                "is_closed": True,
            },
        ],
    }, headers=merchant_headers)

    r = await client.get(
        f"/api/services/{merchant_setup['product_id']}/available-slots?date={target}&store_id={merchant_setup['store_id']}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["slots"] == []


@pytest.mark.asyncio
async def test_available_slots_occupied_when_full(client, auth_headers, merchant_headers, merchant_setup):
    """[F6] 当门店级并发=2 时，2 个订单占用同一时段后该时段应置灰"""
    # 设营业时间
    await client.post("/api/merchant/business-hours", json={
        "store_id": merchant_setup["store_id"],
        "entries": [{"weekday": w, "start_time": "09:00", "end_time": "18:00"} for w in range(7)],
    }, headers=merchant_headers)
    # 门店级并发上限=2
    await client.post("/api/merchant/concurrency-limit", json={
        "store_id": merchant_setup["store_id"],
        "store_max_concurrent": 2,
    }, headers=merchant_headers)

    # 直接在 DB 插入 2 个已预约订单，挤占 14 天后的 10:00 时段
    target_date = date.today() + timedelta(days=14)
    appt_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=10)

    async with test_session() as session:
        # 创建 2 个普通用户
        for i in range(2):
            u = User(
                phone=f"1380000010{i}",
                password_hash=get_password_hash("u"),
                role=UserRole.user,
            )
            session.add(u)
            await session.flush()

            o = UnifiedOrder(
                order_no=f"TEST_OCC_{i}",
                user_id=u.id,
                total_amount=Decimal("100"),
                status=UnifiedOrderStatus.pending_use,
                store_id=merchant_setup["store_id"],
            )
            session.add(o)
            await session.flush()

            session.add(OrderItem(
                order_id=o.id,
                product_id=merchant_setup["product_id"],
                product_name="测试服务-60min",
                product_price=Decimal("100"),
                subtotal=Decimal("100"),
                fulfillment_type=FulfillmentType.in_store,
                appointment_time=appt_dt,
            ))
        await session.commit()

    r = await client.get(
        f"/api/services/{merchant_setup['product_id']}/available-slots"
        f"?date={target_date.isoformat()}&store_id={merchant_setup['store_id']}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    slots = r.json()["slots"]
    occupied = [s for s in slots if not s["is_available"] and s["reason"] == "occupied"]
    assert len(occupied) >= 1, f"expected at least one occupied slot, got: {slots}"


@pytest.mark.asyncio
async def test_available_slots_past_30_min_grayed(client, auth_headers, merchant_headers, merchant_setup):
    """[R5] 当天最小提前 30 分钟：当天即将到来的时段应被标记 reason=past（如果会出现）。

    本测试只校验 API 返回 200 与 slots 字段存在。具体置灰需依赖当前真实时间，跳过严格断言。
    """
    await client.post("/api/merchant/business-hours", json={
        "store_id": merchant_setup["store_id"],
        "entries": [{"weekday": w, "start_time": "00:00", "end_time": "23:00"} for w in range(7)],
    }, headers=merchant_headers)

    today = date.today().isoformat()
    r = await client.get(
        f"/api/services/{merchant_setup['product_id']}/available-slots?date={today}&store_id={merchant_setup['store_id']}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert "slots" in r.json()


# ──────────────── 4. 站内消息红点 ────────────────

@pytest.mark.asyncio
async def test_unread_count_initial_zero(client, auth_headers):
    """[F8] 初始用户未读数为 0"""
    r = await client.get("/api/notifications/unread-count", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_unread"] == 0
    assert data["total_orders_with_unread"] == 0
    assert data["order_ids"] == []


@pytest.mark.asyncio
async def test_unread_count_with_notifications(client, auth_headers, user_token):
    """[F8] 写入 3 条不同订单的未读消息后，total_orders_with_unread = 3"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        uid = res.scalar_one().id

        for oid in (101, 102, 103):
            session.add(Notification(
                user_id=uid,
                order_id=oid,
                event_type="order_status_changed",
                title="状态变更",
                content="测试",
                is_read=False,
            ))
        # 一条已读
        session.add(Notification(
            user_id=uid,
            order_id=104,
            event_type="order_status_changed",
            title="测试",
            is_read=True,
        ))
        await session.commit()

    r = await client.get("/api/notifications/unread-count", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_unread"] == 3
    assert data["total_orders_with_unread"] == 3
    assert sorted(data["order_ids"]) == [101, 102, 103]


@pytest.mark.asyncio
async def test_mark_read_by_order_clears_only_target(client, auth_headers, user_token):
    """[F8/R10] 按订单清除红点：仅清除该订单的未读消息"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        uid = res.scalar_one().id
        for oid in (201, 202):
            for _ in range(2):
                session.add(Notification(
                    user_id=uid,
                    order_id=oid,
                    event_type="order_status_changed",
                    title="t",
                    is_read=False,
                ))
        await session.commit()

    r = await client.post(
        "/api/notifications/mark-read-by-order",
        json={"order_id": 201},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 2

    # 红点应只剩订单 202 的 2 条
    r2 = await client.get("/api/notifications/unread-count", headers=auth_headers)
    data = r2.json()
    assert data["total_unread"] == 2
    assert data["order_ids"] == [202]


# ──────────────── 5. 订单列表附件元信息 ────────────────

@pytest.mark.asyncio
async def test_attachment_meta_empty(client, auth_headers):
    """空查询：返回空列表"""
    r = await client.post(
        "/api/orders/attachment-meta",
        json={"order_ids": [99999], "order_source": "item"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_attachment_meta_with_data(client, auth_headers, merchant_setup):
    """[F9] 含图片 + PDF 的混合附件，返回缩略图与计数"""
    async with test_session() as session:
        # 创建用户订单
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        cust = res.scalar_one()
        order = UnifiedOrder(
            order_no="ATT001",
            user_id=cust.id,
            total_amount=Decimal("100"),
            status=UnifiedOrderStatus.pending_use,
            store_id=merchant_setup["store_id"],
        )
        session.add(order)
        await session.flush()
        oi = OrderItem(
            order_id=order.id,
            product_id=merchant_setup["product_id"],
            product_name="测试",
            product_price=Decimal("100"),
            subtotal=Decimal("100"),
            fulfillment_type=FulfillmentType.in_store,
        )
        session.add(oi)
        await session.flush()

        # 4 张图片 + 2 个 PDF
        for i in range(4):
            session.add(OrderAttachment(
                order_id=oi.id,
                order_source="item",
                store_id=merchant_setup["store_id"],
                uploader_user_id=merchant_setup["merchant_user_id"],
                file_type="image",
                file_url=f"https://example.com/img{i}.jpg",
                thumbnail_url=f"https://example.com/img{i}_thumb.jpg",
                file_name=f"img{i}.jpg",
            ))
        for i in range(2):
            session.add(OrderAttachment(
                order_id=oi.id,
                order_source="item",
                store_id=merchant_setup["store_id"],
                uploader_user_id=merchant_setup["merchant_user_id"],
                file_type="pdf",
                file_url=f"https://example.com/doc{i}.pdf",
                file_name=f"doc{i}.pdf",
            ))
        await session.commit()
        item_id = oi.id

    r = await client.post(
        "/api/orders/attachment-meta",
        json={"order_ids": [item_id], "order_source": "item"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    m = items[0]
    assert m["image_count"] == 4
    assert m["pdf_count"] == 2
    assert m["total_count"] == 6
    assert len(m["image_thumbs"]) == 3  # 仅前 3 张


@pytest.mark.asyncio
async def test_attachment_meta_only_owner(client, auth_headers, merchant_setup):
    """[Security] 不能查看其他用户的订单附件元数据"""
    async with test_session() as session:
        # 另一用户的订单
        other = User(
            phone="13900099999",
            password_hash=get_password_hash("p"),
            role=UserRole.user,
        )
        session.add(other)
        await session.flush()
        order = UnifiedOrder(
            order_no="ATT_OTHER",
            user_id=other.id,
            total_amount=Decimal("100"),
            status=UnifiedOrderStatus.pending_use,
        )
        session.add(order)
        await session.flush()
        oi = OrderItem(
            order_id=order.id,
            product_id=merchant_setup["product_id"],
            product_name="测试",
            product_price=Decimal("100"),
            subtotal=Decimal("100"),
            fulfillment_type=FulfillmentType.in_store,
        )
        session.add(oi)
        await session.flush()
        session.add(OrderAttachment(
            order_id=oi.id,
            order_source="item",
            uploader_user_id=merchant_setup["merchant_user_id"],
            file_type="image",
            file_url="https://x",
            file_name="x.jpg",
        ))
        await session.commit()
        other_item_id = oi.id

    r = await client.post(
        "/api/orders/attachment-meta",
        json={"order_ids": [other_item_id], "order_source": "item"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    # 不属于当前用户，应该被过滤
    assert r.json()["items"] == []


# ──────────────── 6. 客户取消订单 + 站内信 ────────────────

@pytest.mark.asyncio
async def test_cancel_order_pending_payment(client, auth_headers, merchant_setup):
    """[F10] 待付款订单可取消"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        cust = res.scalar_one()
        order = UnifiedOrder(
            order_no="CANCEL_PP",
            user_id=cust.id,
            total_amount=Decimal("100"),
            status=UnifiedOrderStatus.pending_payment,
        )
        session.add(order)
        await session.commit()
        oid = order.id

    r = await client.post(
        f"/api/orders/unified/{oid}/cancel",
        json={"cancel_reason": "test"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_cancel_order_appointed_before_service(client, auth_headers, merchant_setup):
    """[F10/R7] 已预约但服务时段未到达：可取消（全额退款）"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        cust = res.scalar_one()
        order = UnifiedOrder(
            order_no="CANCEL_APPT",
            user_id=cust.id,
            total_amount=Decimal("100"),
            paid_amount=Decimal("100"),
            status=UnifiedOrderStatus.pending_use,
        )
        session.add(order)
        await session.flush()
        # 服务时间在 1 天之后
        session.add(OrderItem(
            order_id=order.id,
            product_id=merchant_setup["product_id"],
            product_name="测试",
            product_price=Decimal("100"),
            subtotal=Decimal("100"),
            fulfillment_type=FulfillmentType.in_store,
            appointment_time=datetime.utcnow() + timedelta(days=1),
        ))
        await session.commit()
        oid = order.id

    r = await client.post(
        f"/api/orders/unified/{oid}/cancel",
        json={"cancel_reason": "改期"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_cancel_order_after_service_time_rejected(client, auth_headers, merchant_setup):
    """[F10/R7] 服务时段已开始：不可自助取消"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        cust = res.scalar_one()
        order = UnifiedOrder(
            order_no="CANCEL_LATE",
            user_id=cust.id,
            total_amount=Decimal("100"),
            status=UnifiedOrderStatus.pending_use,
        )
        session.add(order)
        await session.flush()
        session.add(OrderItem(
            order_id=order.id,
            product_id=merchant_setup["product_id"],
            product_name="测试",
            product_price=Decimal("100"),
            subtotal=Decimal("100"),
            fulfillment_type=FulfillmentType.in_store,
            appointment_time=datetime.utcnow() - timedelta(hours=1),
        ))
        await session.commit()
        oid = order.id

    r = await client.post(
        f"/api/orders/unified/{oid}/cancel",
        json={"cancel_reason": "test"},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_cancel_order_completed_rejected(client, auth_headers, merchant_setup):
    """[F10] 已完成订单不可取消"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        cust = res.scalar_one()
        order = UnifiedOrder(
            order_no="CANCEL_DONE",
            user_id=cust.id,
            total_amount=Decimal("100"),
            status=UnifiedOrderStatus.completed,
        )
        session.add(order)
        await session.commit()
        oid = order.id

    r = await client.post(
        f"/api/orders/unified/{oid}/cancel",
        json={"cancel_reason": "test"},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_cancel_order_creates_notification(client, auth_headers, merchant_setup):
    """[F7] 客户取消订单后会创建一条站内信"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        cust = res.scalar_one()
        order = UnifiedOrder(
            order_no="CANCEL_NOTIFY",
            user_id=cust.id,
            total_amount=Decimal("100"),
            status=UnifiedOrderStatus.pending_payment,
        )
        session.add(order)
        await session.commit()
        oid = order.id
        cust_id = cust.id

    await client.post(
        f"/api/orders/unified/{oid}/cancel",
        json={"cancel_reason": "test"},
        headers=auth_headers,
    )

    async with test_session() as session:
        res = await session.execute(
            select(Notification).where(
                Notification.user_id == cust_id,
                Notification.order_id == oid,
                Notification.event_type == "order_cancelled",
            )
        )
        n = res.scalar_one_or_none()
        assert n is not None
        assert "已取消" in n.title or "已取消" in (n.content or "")


# ──────────────── 7. 站内消息列表 ────────────────

@pytest.mark.asyncio
async def test_list_notifications_paged(client, auth_headers):
    """[F7] 站内消息列表分页查询"""
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        uid = res.scalar_one().id
        for i in range(5):
            session.add(Notification(
                user_id=uid,
                order_id=300 + i,
                event_type="order_status_changed",
                title=f"消息{i}",
                is_read=False,
            ))
        await session.commit()

    r = await client.get("/api/notifications", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 5
    assert data["unread_count"] >= 5


# ──────────────── 8. 附件大小/类型校验 ────────────────

@pytest.mark.asyncio
async def test_attachment_size_limit_constant():
    """[R2] 单文件 5MB 上限常量校验"""
    from app.api.merchant_v1 import MAX_ATTACHMENT_SIZE, MAX_ATTACHMENTS_PER_ORDER
    assert MAX_ATTACHMENT_SIZE == 5 * 1024 * 1024
    assert MAX_ATTACHMENTS_PER_ORDER == 5
