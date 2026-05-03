"""[PRD「订单状态自动推进策略」v1.0 / v2.0 简化] 后端测试

注意：v2.0「订单状态机简化方案」已下线 R1，新增 T-1 18:00 提醒。
本文件保留与新逻辑兼容的用例（R2 + 懒兜底兼容 + admin categories Bug 修复回归）。
全新场景的用例参见 test_orders_status_simplification.py。
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    OrderItem,
    Product,
    ProductCategory,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from app.tasks.order_status_auto_progress import (
    _do_r2,
    lazy_progress_order,
)
from tests.conftest import test_session


# ────────────── helpers ──────────────


async def _seed_user(phone: str = "13900099999") -> int:
    async with test_session() as db:
        u = User(phone=phone, password_hash="x", nickname="T", role="user")
        db.add(u)
        await db.commit()
        return u.id


async def _seed_order_with_appt(
    user_id: int,
    *,
    status: UnifiedOrderStatus,
    appt: datetime,
    used_count: int = 0,
    order_no: str = "AUTO_TEST_001",
) -> int:
    async with test_session() as db:
        order = UnifiedOrder(
            order_no=order_no,
            user_id=user_id,
            total_amount=99.0,
            paid_amount=99.0,
            status=status,
            paid_at=datetime.utcnow(),
        )
        db.add(order)
        await db.flush()
        # 简化的 OrderItem，不强依赖 Product/Sku
        item = OrderItem(
            order_id=order.id,
            product_id=1,
            product_name="测试服务",
            product_price=99.0,
            quantity=1,
            subtotal=99.0,
            fulfillment_type="in_store",
            appointment_time=appt,
            total_redeem_count=1,
            used_redeem_count=used_count,
        )
        db.add(item)
        await db.commit()
        return order.id


# ────────────── R1 已下线（PRD v2.0 简化方案） ──────────────
# 旧的 R1 测试已迁移到 test_orders_status_simplification.py 中，
# 此处不再保留 R1 翻转专属用例。


# ────────────── R2 测试 ──────────────


@pytest.mark.asyncio
async def test_r2_flips_back_to_pending_appointment_when_overdue_unused():
    """R2：pending_use + 预约日 < 今天 + 未核销 → pending_appointment（清空 appointment_time）。"""
    uid = await _seed_user("13900100003")
    appt_yesterday = datetime.utcnow() - timedelta(days=1, hours=1)
    oid = await _seed_order_with_appt(
        uid, status=UnifiedOrderStatus.pending_use, appt=appt_yesterday,
        used_count=0, order_no="R2_OVERDUE_001",
    )
    async with test_session() as db:
        affected = await _do_r2(db)
        await db.commit()
    assert affected == 1
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        st = order.status.value if hasattr(order.status, "value") else order.status
        assert st == "pending_appointment"
        # appointment_time 应被清空
        items = (await db.execute(select(OrderItem).where(OrderItem.order_id == oid))).scalars().all()
        assert all(it.appointment_time is None for it in items)


@pytest.mark.asyncio
async def test_r2_skips_partially_used_orders():
    """R2：pending_use + 预约日 < 今天 + 已部分核销 → 保持 pending_use。"""
    uid = await _seed_user("13900100004")
    appt_yesterday = datetime.utcnow() - timedelta(days=1, hours=1)
    oid = await _seed_order_with_appt(
        uid, status=UnifiedOrderStatus.pending_use, appt=appt_yesterday,
        used_count=1, order_no="R2_USED_001",
    )
    async with test_session() as db:
        affected = await _do_r2(db)
        await db.commit()
    assert affected == 0
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        st = order.status.value if hasattr(order.status, "value") else order.status
        assert st == "pending_use"


# ────────────── 懒兜底测试 ──────────────


@pytest.mark.asyncio
async def test_lazy_progress_r1_when_opening_order_detail():
    """[PRD v2.0 兼容] 懒兜底：历史 appointed 订单（任何预约时间）→ 即翻 pending_use。"""
    uid = await _seed_user("13900100005")
    appt_today = datetime.utcnow() - timedelta(minutes=30)
    oid = await _seed_order_with_appt(
        uid, status=UnifiedOrderStatus.appointed, appt=appt_today, order_no="LAZY_R1_001"
    )
    async with test_session() as db:
        from sqlalchemy.orm import selectinload
        order = (await db.execute(
            select(UnifiedOrder).options(selectinload(UnifiedOrder.items)).where(UnifiedOrder.id == oid)
        )).scalar_one()
        changed = await lazy_progress_order(order, db)
        await db.commit()
    assert changed is True
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        st = order.status.value if hasattr(order.status, "value") else order.status
        assert st == "pending_use"  # 兼容老订单：appointed → pending_use


@pytest.mark.asyncio
async def test_lazy_progress_r2_when_opening_overdue_order():
    """懒兜底：pending_use 且预约日 < 今天 + 未核销，调用一次即退回 pending_appointment。"""
    uid = await _seed_user("13900100006")
    appt_yesterday = datetime.utcnow() - timedelta(days=2)
    oid = await _seed_order_with_appt(
        uid, status=UnifiedOrderStatus.pending_use, appt=appt_yesterday,
        used_count=0, order_no="LAZY_R2_001",
    )
    async with test_session() as db:
        from sqlalchemy.orm import selectinload
        order = (await db.execute(
            select(UnifiedOrder).options(selectinload(UnifiedOrder.items)).where(UnifiedOrder.id == oid)
        )).scalar_one()
        changed = await lazy_progress_order(order, db)
        await db.commit()
    assert changed is True
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        st = order.status.value if hasattr(order.status, "value") else order.status
        assert st == "pending_appointment"


@pytest.mark.asyncio
async def test_lazy_progress_no_change_for_future_pending_use():
    """[PRD v2.0] 懒兜底：pending_use + 预约日为未来 → 不动。"""
    uid = await _seed_user("13900100007")
    appt_future = datetime.utcnow() + timedelta(days=3)
    oid = await _seed_order_with_appt(
        uid, status=UnifiedOrderStatus.pending_use, appt=appt_future, order_no="LAZY_NOOP_001"
    )
    async with test_session() as db:
        from sqlalchemy.orm import selectinload
        order = (await db.execute(
            select(UnifiedOrder).options(selectinload(UnifiedOrder.items)).where(UnifiedOrder.id == oid)
        )).scalar_one()
        changed = await lazy_progress_order(order, db)
    assert changed is False


# ────────────── Bug 修复验证：admin categories 接口 ──────────────


@pytest.mark.asyncio
async def test_admin_categories_endpoint_exists(client: AsyncClient, admin_headers):
    """admin /api/admin/products/categories 应可访问（200 + 返回列表/分页结构）。

    这是订单明细页「全部分类」下拉的正确数据源，验证下拉数据可拉到。
    """
    # 先建一个分类，确保接口能查到数据
    async with test_session() as db:
        db.add(ProductCategory(name="测试分类", status="active", sort_order=0, level=1))
        await db.commit()

    res = await client.get("/api/admin/products/categories", headers=admin_headers)
    assert res.status_code == 200, f"分类接口异常: {res.status_code} {res.text[:300]}"
    data = res.json()
    # 兼容三种可能返回结构：list / {items} / {list}
    if isinstance(data, list):
        items = data
    else:
        items = data.get("items") or data.get("list") or data.get("data") or []
    assert isinstance(items, list)
    assert any(c.get("name") == "测试分类" for c in items)


@pytest.mark.asyncio
async def test_wrong_path_product_system_categories_does_not_exist(client: AsyncClient, admin_headers):
    """断言曾经的错误路径 /api/admin/product-system/categories 不存在（应 404 或 405）。

    这是 PRD「Bug 修复」的根因：前端误调用此地址才导致下拉框为空。
    """
    res = await client.get("/api/admin/product-system/categories", headers=admin_headers)
    # 任何非 2xx 都说明该路径确实不可用，与 PRD 一致
    assert res.status_code >= 400, (
        f"错误路径竟然存在，PRD 描述与实际不符: status={res.status_code}"
    )
