"""[PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛红点统一计数 + 抽屉订单 6 状态合并 验收测试。

覆盖：
- /badge 旧字段向后兼容 + 新增 medication / order / breakdown 嵌套字段
- /badge 6 个订单状态合并计数：pending_payment / pending_appointment / appointed
  / pending_use / partial_used / pending_receipt
- /badge has_urgent 计算：过点未服用 medication.has_urgent=True；存在 pending_payment → order.has_urgent=True
- /badge 排除终态：pending_shipment / refunding / completed / cancelled 不计入红点
- /appointments 默认返回 6 状态合并；支持 status_in 参数过滤；扩展字段 status / amount / remaining_redeem_count 等
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FulfillmentType,
    MedicationPlan,
    OrderItem,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)

PREFIX = "/api/medication-reminder"


async def _user_id(client: AsyncClient, headers) -> int:
    """从 /api/auth/me 读到当前用户 id（避免直查 DB 的 fixture 依赖）。"""
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return int(r.json()["id"])


async def _create_order(
    user_id: int,
    status: UnifiedOrderStatus,
    *,
    total_amount: float = 99.0,
    product_name: str = "测试商品",
    verification_code: str | None = None,
    appointment_time: datetime | None = None,
    total_redeem_count: int = 1,
    used_redeem_count: int = 0,
) -> int:
    from tests.conftest import test_session

    async with test_session() as db:
        order = UnifiedOrder(
            order_no=f"UO_BELL_{datetime.now().timestamp() * 1000:.0f}_{status.value}",
            user_id=user_id,
            total_amount=total_amount,
            paid_amount=total_amount if status != UnifiedOrderStatus.pending_payment else 0,
            status=status,
        )
        db.add(order)
        await db.flush()
        item = OrderItem(
            order_id=order.id,
            product_id=1,
            product_name=product_name,
            product_price=total_amount,
            quantity=1,
            subtotal=total_amount,
            fulfillment_type=FulfillmentType.in_store,
            verification_code=verification_code,
            appointment_time=appointment_time,
            total_redeem_count=total_redeem_count,
            used_redeem_count=used_redeem_count,
        )
        db.add(item)
        await db.commit()
        return order.id


# ──────────────── /badge：合并计数 + 新字段 ────────────────


@pytest.mark.asyncio
async def test_badge_zero_includes_new_fields(client: AsyncClient, auth_headers):
    r = await client.get(f"{PREFIX}/badge", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # 旧字段
    assert body["medication_unchecked"] == 0
    assert body["appointment_pending"] == 0
    assert body["total"] == 0
    # 新字段
    assert "medication" in body and "order" in body
    assert body["medication"]["count"] == 0
    assert body["medication"]["has_urgent"] is False
    assert body["order"]["count"] == 0
    assert body["order"]["has_urgent"] is False
    bd = body["order"]["breakdown"]
    for k in [
        "pending_payment",
        "pending_appointment",
        "appointed",
        "pending_use",
        "partial_used",
        "pending_receipt",
    ]:
        assert bd[k] == 0


@pytest.mark.asyncio
async def test_badge_merges_six_order_statuses(client: AsyncClient, auth_headers):
    uid = await _user_id(client, auth_headers)
    # 6 个待办状态各 1 单
    await _create_order(uid, UnifiedOrderStatus.pending_payment)
    await _create_order(uid, UnifiedOrderStatus.pending_appointment)
    await _create_order(uid, UnifiedOrderStatus.appointed)
    await _create_order(uid, UnifiedOrderStatus.pending_use, verification_code="V001")
    await _create_order(
        uid, UnifiedOrderStatus.partial_used, total_redeem_count=3, used_redeem_count=1
    )
    await _create_order(uid, UnifiedOrderStatus.pending_receipt)
    # 终态不计入红点
    await _create_order(uid, UnifiedOrderStatus.pending_shipment)
    await _create_order(uid, UnifiedOrderStatus.completed)

    r = await client.get(f"{PREFIX}/badge", headers=auth_headers)
    body = r.json()
    assert body["order"]["count"] == 6
    assert body["appointment_pending"] == 6  # 旧字段同步反映合并值
    bd = body["order"]["breakdown"]
    assert bd["pending_payment"] == 1
    assert bd["pending_appointment"] == 1
    assert bd["appointed"] == 1
    assert bd["pending_use"] == 1
    assert bd["partial_used"] == 1
    assert bd["pending_receipt"] == 1
    # pending_payment 存在 → order.has_urgent=True
    assert body["order"]["has_urgent"] is True
    assert body["total"] == 6


@pytest.mark.asyncio
async def test_badge_medication_overdue_urgent(
    client: AsyncClient, auth_headers, db_session
):
    """过点未服用 → medication.has_urgent = True。"""
    uid = await _user_id(client, auth_headers)
    # 创建一个 00:01 时刻就会过点的用药计划（当前时间一定 >= 00:01 除非凌晨刚过 00:00）
    # 为稳健起见用 00:00 时刻
    plan_payload = {
        "drug_name": "降压药",
        "dosage": "1片",
        "schedule": ["00:00"],
    }
    r = await client.post(f"{PREFIX}/plans", headers=auth_headers, json=plan_payload)
    assert r.status_code == 200, r.text

    r2 = await client.get(f"{PREFIX}/badge", headers=auth_headers)
    body = r2.json()
    assert body["medication"]["count"] == 1
    # 00:00 一定 < 当前时间（除非测试在 00:00:00 整运行，概率极低）
    assert body["medication"]["has_urgent"] is True
    assert body["medication_unchecked"] == 1


@pytest.mark.asyncio
async def test_badge_no_urgent_when_future_only(client: AsyncClient, auth_headers):
    """计划时间在未来（23:59）→ medication.has_urgent = False。"""
    r = await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "VC", "dosage": "1片", "schedule": ["23:59"]},
    )
    assert r.status_code == 200
    b = (await client.get(f"{PREFIX}/badge", headers=auth_headers)).json()
    # 计划数=1，但若当前时刻 < 23:59 则非紧急
    if datetime.now().strftime("%H:%M") < "23:59":
        assert b["medication"]["has_urgent"] is False
    assert b["medication"]["count"] == 1


@pytest.mark.asyncio
async def test_badge_total_equals_med_plus_order(client: AsyncClient, auth_headers):
    uid = await _user_id(client, auth_headers)
    await _create_order(uid, UnifiedOrderStatus.appointed)
    await _create_order(uid, UnifiedOrderStatus.pending_receipt)
    await client.post(
        f"{PREFIX}/plans",
        headers=auth_headers,
        json={"drug_name": "A", "dosage": "1片", "schedule": ["09:00", "21:00"]},
    )
    b = (await client.get(f"{PREFIX}/badge", headers=auth_headers)).json()
    assert b["total"] == b["medication"]["count"] + b["order"]["count"]
    assert b["total"] == 2 + 2  # 2 单 + 2 次用药


# ──────────────── /appointments：6 状态合并 + 扩展字段 ────────────────


@pytest.mark.asyncio
async def test_appointments_default_returns_six_statuses(
    client: AsyncClient, auth_headers
):
    uid = await _user_id(client, auth_headers)
    for s in [
        UnifiedOrderStatus.pending_payment,
        UnifiedOrderStatus.pending_appointment,
        UnifiedOrderStatus.appointed,
        UnifiedOrderStatus.pending_use,
        UnifiedOrderStatus.partial_used,
        UnifiedOrderStatus.pending_receipt,
    ]:
        await _create_order(uid, s)
    # 终态：不应出现
    await _create_order(uid, UnifiedOrderStatus.completed)
    await _create_order(uid, UnifiedOrderStatus.pending_shipment)

    r = await client.get(f"{PREFIX}/appointments", headers=auth_headers)
    assert r.status_code == 200, r.text
    arr = r.json()
    assert len(arr) == 6
    statuses = {x["status"] for x in arr}
    assert statuses == {
        "pending_payment",
        "pending_appointment",
        "appointed",
        "pending_use",
        "partial_used",
        "pending_receipt",
    }


@pytest.mark.asyncio
async def test_appointments_status_in_filter(client: AsyncClient, auth_headers):
    uid = await _user_id(client, auth_headers)
    await _create_order(uid, UnifiedOrderStatus.pending_payment)
    await _create_order(uid, UnifiedOrderStatus.appointed)
    await _create_order(uid, UnifiedOrderStatus.pending_receipt)

    r = await client.get(
        f"{PREFIX}/appointments?status_in=pending_payment,pending_receipt",
        headers=auth_headers,
    )
    arr = r.json()
    assert len(arr) == 2
    assert {x["status"] for x in arr} == {"pending_payment", "pending_receipt"}


@pytest.mark.asyncio
async def test_appointments_includes_extended_fields(client: AsyncClient, auth_headers):
    uid = await _user_id(client, auth_headers)
    await _create_order(
        uid,
        UnifiedOrderStatus.partial_used,
        product_name="次卡-按摩",
        total_amount=288.0,
        total_redeem_count=10,
        used_redeem_count=3,
        verification_code="VC-9999",
    )
    r = await client.get(f"{PREFIX}/appointments", headers=auth_headers)
    arr = r.json()
    assert len(arr) == 1
    it = arr[0]
    assert it["status"] == "partial_used"
    assert it["status_text"] == "部分核销"
    assert it["amount"] == "288.00"
    assert it["service_name"] == "次卡-按摩"
    assert it["remaining_redeem_count"] == 7
    assert it["total_redeem_count"] == 10
    assert it["verification_code"] == "VC-9999"
    assert it["created_at"] is not None


@pytest.mark.asyncio
async def test_appointments_status_text_localized(client: AsyncClient, auth_headers):
    uid = await _user_id(client, auth_headers)
    await _create_order(uid, UnifiedOrderStatus.pending_payment)
    await _create_order(uid, UnifiedOrderStatus.pending_appointment)
    arr = (await client.get(f"{PREFIX}/appointments", headers=auth_headers)).json()
    text_map = {x["status"]: x["status_text"] for x in arr}
    assert text_map["pending_payment"] == "待支付"
    assert text_map["pending_appointment"] == "待预约"


@pytest.mark.asyncio
async def test_appointments_unknown_status_ignored(client: AsyncClient, auth_headers):
    """无效 status_in 值会被忽略，回落到 6 状态默认集。"""
    uid = await _user_id(client, auth_headers)
    await _create_order(uid, UnifiedOrderStatus.appointed)
    r = await client.get(
        f"{PREFIX}/appointments?status_in=foo,bar,baz", headers=auth_headers
    )
    arr = r.json()
    # 全部解析失败 → fallback 到 6 状态默认集
    assert len(arr) >= 1
    assert all(
        x["status"]
        in {
            "pending_payment",
            "pending_appointment",
            "appointed",
            "pending_use",
            "partial_used",
            "pending_receipt",
        }
        for x in arr
    )
