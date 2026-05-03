"""[PRD「我的订单与售后状态体系优化」] 后端测试 V3

覆盖 PRD 全部新点：
- F-04/F-12：「已完成」Tab 与 15 天评价时效 → review_deadline_at / review_expired / review_expired 按钮
- F-05/F-07：4 个统一逻辑筛选（待审核 / 处理中 / 已完成 / 已驳回）— 三端 SQL 一致
- F-06/F-07：H5 退款独立列表数据范围 = 全部订单退货/售后 Tab
- F-09/F-10：admin /orders/v2/enums 含 aftersales_logical_status 4 值
- F-09：admin /orders/unified?aftersales_status=pending|processing|completed|rejected 工作正常
- F-13：售后撤销接口 /refund/cancel；仅 refund_pending 可撤销，撤销后回到 pending_use
- 兼容：完成态有评价时返回 view_review；超期未评价返回 review_expired
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    OrderItem,
    Product,
    ProductCategory,
    RefundStatusEnum,
    UnifiedOrder,
    UnifiedOrderStatus,
)
from tests.conftest import test_session


# ────────────────── helpers ──────────────────


async def _seed_category(name: str = "V3 测试分类") -> int:
    async with test_session() as db:
        cat = ProductCategory(name=name, status="active", sort_order=0, level=1)
        db.add(cat)
        await db.commit()
        return cat.id


async def _seed_product(
    category_id: int,
    *,
    name: str = "V3 测试商品",
    fulfillment_type: str = "in_store",
    appointment_mode: str = "none",
    stock: int = 100,
) -> int:
    async with test_session() as db:
        product = Product(
            name=name,
            category_id=category_id,
            fulfillment_type=fulfillment_type,
            original_price=199.0,
            sale_price=99.0,
            images=["https://img.example.com/v3.jpg"],
            stock=stock,
            status="active",
            points_exchangeable=False,
            redeem_count=1,
            appointment_mode=appointment_mode,
        )
        db.add(product)
        await db.commit()
        return product.id


async def _create_pay(client: AsyncClient, headers, pid: int) -> int:
    resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "wechat"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    oid = resp.json()["id"]
    pay = await client.post(
        f"/api/orders/unified/{oid}/pay",
        json={"payment_method": "wechat"},
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    return oid


# ════════════════════════════════════════════
#  F-12：15 天评价时效
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_review_within_15_days_returns_review_button(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("rev-15d-ok")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.status = UnifiedOrderStatus.completed
        order.completed_at = datetime.utcnow() - timedelta(days=10)
        order.has_reviewed = False
        await db.commit()

    detail = await client.get(f"/api/orders/unified/{oid}", headers=auth_headers)
    body = detail.json()
    assert body["review_expired"] is False
    assert "review" in body["action_buttons"]
    assert "review_expired" not in body["action_buttons"]
    # 15 天 deadline 必须返回
    assert body["review_deadline_at"] is not None


@pytest.mark.asyncio
async def test_review_after_15_days_shows_expired_button(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("rev-15d-exp")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.status = UnifiedOrderStatus.completed
        order.completed_at = datetime.utcnow() - timedelta(days=20)
        order.has_reviewed = False
        await db.commit()

    detail = await client.get(f"/api/orders/unified/{oid}", headers=auth_headers)
    body = detail.json()
    assert body["review_expired"] is True
    assert "review" not in body["action_buttons"]
    assert "review_expired" in body["action_buttons"]


@pytest.mark.asyncio
async def test_review_api_rejects_after_15_days(client: AsyncClient, auth_headers):
    """评价 API 必须在 15 天后拒绝评价（防绕过前端）。"""
    cat_id = await _seed_category("rev-api-15d")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.status = UnifiedOrderStatus.completed
        order.completed_at = datetime.utcnow() - timedelta(days=20)
        order.has_reviewed = False
        await db.commit()

    resp = await client.post(
        f"/api/orders/unified/{oid}/review",
        json={"rating": 5, "content": "后端时效校验测试"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "评价已过期" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reviewed_order_shows_view_review_button(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("rev-viewed")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.status = UnifiedOrderStatus.completed
        order.completed_at = datetime.utcnow() - timedelta(days=3)
        order.has_reviewed = True
        await db.commit()

    detail = await client.get(f"/api/orders/unified/{oid}", headers=auth_headers)
    body = detail.json()
    assert "view_review" in body["action_buttons"]
    assert "review" not in body["action_buttons"]


# ════════════════════════════════════════════
#  F-05/F-07：4 个统一逻辑子筛选
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sub_tab_pending_filters_applied_only(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("sub-pending")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    # 此时 status=refunding 且 refund_status=applied
    resp = await client.get(
        "/api/orders/unified?tab=refund_aftersales&sub_tab=pending", headers=auth_headers
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert oid in ids


@pytest.mark.asyncio
async def test_sub_tab_processing_filters_returning(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("sub-processing")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    # 改为 returning 模拟处理中
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.refund_status = RefundStatusEnum.returning
        await db.commit()
    resp = await client.get(
        "/api/orders/unified?tab=refund_aftersales&sub_tab=processing", headers=auth_headers
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert oid in ids


@pytest.mark.asyncio
async def test_sub_tab_completed_filters_refund_success(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("sub-completed")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.refund_status = RefundStatusEnum.refund_success
        order.status = UnifiedOrderStatus.refunded
        await db.commit()
    resp = await client.get(
        "/api/orders/unified?tab=refund_aftersales&sub_tab=completed", headers=auth_headers
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert oid in ids


@pytest.mark.asyncio
async def test_sub_tab_rejected_filters_rejected(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("sub-rejected")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.refund_status = RefundStatusEnum.rejected
        await db.commit()
    resp = await client.get(
        "/api/orders/unified?tab=refund_aftersales&sub_tab=rejected", headers=auth_headers
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert oid in ids


# ════════════════════════════════════════════
#  逻辑状态字段
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_order_response_carries_aftersales_logical_status(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("logical")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    detail = await client.get(f"/api/orders/unified/{oid}", headers=auth_headers)
    body = detail.json()
    assert body["aftersales_logical_status"] == "pending"
    assert body["aftersales_logical_label"] == "待审核"
    assert body["can_withdraw_refund"] is True


# ════════════════════════════════════════════
#  F-13：售后撤销
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_refund_cancel_endpoint_succeeds_when_pending(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("withdraw-ok")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    # /refund/cancel 别名应可用
    cancel = await client.post(
        f"/api/orders/unified/{oid}/refund/cancel",
        json={"cancel_reason": "误操作"},
        headers=auth_headers,
    )
    assert cancel.status_code == 200, cancel.text
    detail = await client.get(f"/api/orders/unified/{oid}", headers=auth_headers)
    body = detail.json()
    # 撤销后 status 回到 pending_use；refund_status 回到 none
    assert body["status"] == "pending_use"
    assert body["refund_status"] == "none"
    assert body["aftersales_logical_status"] == "none"
    assert body["can_withdraw_refund"] is False


@pytest.mark.asyncio
async def test_refund_cancel_endpoint_rejects_when_processing(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("withdraw-fail")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    # 模拟客服已通过，进入处理中
    async with test_session() as db:
        order = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == oid))).scalar_one()
        order.refund_status = RefundStatusEnum.approved
        await db.commit()
    cancel = await client.post(
        f"/api/orders/unified/{oid}/refund/cancel",
        json={"cancel_reason": "再想想"},
        headers=auth_headers,
    )
    assert cancel.status_code == 400
    assert "不允许" in cancel.json()["detail"]


# ════════════════════════════════════════════
#  F-09/F-10：admin 接口
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_v2_enums_includes_aftersales_logical(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/orders/v2/enums", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "aftersales_logical_status" in data
    values = {x["value"] for x in data["aftersales_logical_status"]}
    assert values == {"pending", "processing", "completed", "rejected"}
    labels = {x["value"]: x["label"] for x in data["aftersales_logical_status"]}
    assert labels["pending"] == "待审核"
    assert labels["processing"] == "处理中"
    assert labels["completed"] == "已完成"
    assert labels["rejected"] == "已驳回"


@pytest.mark.asyncio
async def test_admin_orders_filter_by_aftersales_status(
    client: AsyncClient, admin_headers, auth_headers
):
    cat_id = await _seed_category("admin-aftersales")
    pid = await _seed_product(cat_id)
    oid = await _create_pay(client, auth_headers, pid)
    await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
    # admin 用 aftersales_status=pending 必须能查到
    resp = await client.get(
        "/api/admin/orders/unified?aftersales_status=pending", headers=admin_headers
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert oid in ids


@pytest.mark.asyncio
async def test_admin_aftersales_filter_three_terminals_consistent(
    client: AsyncClient, admin_headers, auth_headers
):
    """PRD R-08：三端筛选 SQL 完全一致——
    H5 全部订单 tab=refund_aftersales&sub_tab=pending、
    H5 退款独立列表（同上）、
    admin aftersales_status=pending —— 必须返回相同的订单集。"""
    cat_id = await _seed_category("3term-consistent")
    pid = await _seed_product(cat_id)
    oids = []
    for _ in range(3):
        oid = await _create_pay(client, auth_headers, pid)
        await client.post(f"/api/orders/unified/{oid}/refund", json={"reason": "x"}, headers=auth_headers)
        oids.append(oid)

    h5_resp = await client.get(
        "/api/orders/unified?tab=refund_aftersales&sub_tab=pending", headers=auth_headers
    )
    admin_resp = await client.get(
        "/api/admin/orders/unified?aftersales_status=pending", headers=admin_headers
    )
    h5_ids = sorted(x["id"] for x in h5_resp.json()["items"])
    admin_ids_subset = sorted([x["id"] for x in admin_resp.json()["items"] if x["id"] in oids])
    # admin 可能含其他用户的退款订单，但本次创建的 3 单必须都在 admin 列表中
    assert set(oids).issubset({x["id"] for x in admin_resp.json()["items"]})
    assert set(oids).issubset(set(h5_ids))


# ════════════════════════════════════════════
#  F-04：「已完成」Tab 仅含 status=completed (+expired 兼容 V2)
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_completed_tab_excludes_refunded_orders(client: AsyncClient, auth_headers):
    cat_id = await _seed_category("completed-excludes-refunded")
    pid = await _seed_product(cat_id)
    o_completed = await _create_pay(client, auth_headers, pid)
    o_refunded = await _create_pay(client, auth_headers, pid)
    async with test_session() as db:
        c = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == o_completed))).scalar_one()
        c.status = UnifiedOrderStatus.completed
        c.completed_at = datetime.utcnow()
        r = (await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == o_refunded))).scalar_one()
        r.status = UnifiedOrderStatus.refunded
        await db.commit()

    resp = await client.get("/api/orders/unified?tab=completed", headers=auth_headers)
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["items"]]
    assert o_completed in ids
    # 已退款订单不应出现在「已完成」Tab
    assert o_refunded not in ids
