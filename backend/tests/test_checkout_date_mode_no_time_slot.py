"""[预约日期模式支付页误显示「选择时段」 Bug 修复 v1.0] 后端测试

覆盖场景：
- TC1: date 模式商品下单——只传 date，不传 time_slot，应当 200 创建成功
- TC2: date 模式商品下单——误传 time_slot，后端必须主动忽略；订单 appointment_data 不带 time_slot
- TC3: time_slot 模式商品下单——完整传 date + time_slot，应当 200 创建成功且回传完整数据
- TC4: none 模式商品下单——下单成功，订单不携带任何预约信息
- TC5: 订单详情接口必须透传 OrderItem.appointment_mode 字段（与本次修复联动）

设计依据：bug 文档 §6.1（自动化用例）。
"""

import pytest
from httpx import AsyncClient


async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_product(
    client: AsyncClient,
    admin_headers,
    *,
    name: str,
    cat_name: str,
    appointment_mode: str,
    purchase_appt_mode: str = "purchase_with_appointment",
) -> int:
    """创建测试商品。默认 purchase_appointment_mode=purchase_with_appointment（下单即预约），
    便于在 create_unified_order 路径直接走 appointment_time/appointment_data 校验链路。"""
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": "in_store",
        "original_price": 100.0,
        "sale_price": 99.0,
        "stock": 100,
        "status": "active",
        "images": ["https://example.com/test.jpg"],
        "appointment_mode": appointment_mode,
        "advance_days": 7,
        "include_today": True,
        "daily_quota": 50,
        "purchase_appointment_mode": purchase_appt_mode,
    }
    if appointment_mode == "time_slot":
        payload["time_slots"] = [
            {"start": "09:00", "end": "10:00", "capacity": 5},
            {"start": "10:00", "end": "11:00", "capacity": 5},
        ]
    resp = await client.post(
        "/api/admin/products",
        json=payload,
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _future_date_iso(days_from_today: int = 1) -> str:
    from datetime import date, timedelta
    return (date.today() + timedelta(days=days_from_today)).isoformat()


@pytest.mark.asyncio
async def test_tc1_date_mode_create_order_without_time_slot_succeeds(
    client: AsyncClient, admin_headers, auth_headers
):
    """date 模式：仅传 date，不传 time_slot → 200 OK；订单 appointment_data 不含 time_slot。"""
    pid = await _create_product(
        client, admin_headers,
        name="DateMode·NoSlot商品",
        cat_name="CheckoutDateMode-Cat1",
        appointment_mode="date",
    )
    appt_date = _future_date_iso(1)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{
                "product_id": pid,
                "quantity": 1,
                "appointment_time": f"{appt_date}T00:00:00",
                "appointment_data": {"date": appt_date, "note": "date 模式无时段"},
            }],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, (
        f"date 模式只传 date 应该 200 创建成功；实际 status={resp.status_code} body={resp.text}"
    )
    order_id = resp.json()["id"]
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.status_code == 200
    item = detail.json()["items"][0]
    appt_data = item.get("appointment_data") or {}
    if isinstance(appt_data, dict):
        assert "time_slot" not in appt_data or not appt_data.get("time_slot"), (
            f"date 模式订单的 appointment_data 不应包含 time_slot；实际={appt_data}"
        )


@pytest.mark.asyncio
async def test_tc2_date_mode_ignores_misdelivered_time_slot(
    client: AsyncClient, admin_headers, auth_headers
):
    """date 模式：前端误传 time_slot，后端必须主动忽略，订单 appointment_data 不应保留 time_slot。"""
    pid = await _create_product(
        client, admin_headers,
        name="DateMode·MisSlot商品",
        cat_name="CheckoutDateMode-Cat2",
        appointment_mode="date",
    )
    appt_date = _future_date_iso(1)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{
                "product_id": pid,
                "quantity": 1,
                "appointment_time": f"{appt_date}T00:00:00",
                "appointment_data": {
                    "date": appt_date,
                    "time_slot": "10:00-11:00",  # ← 误传
                },
            }],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, (
        f"date 模式误传 time_slot 应当被后端忽略并 200 OK；实际 status={resp.status_code} body={resp.text}"
    )
    order_id = resp.json()["id"]
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.status_code == 200
    item = detail.json()["items"][0]
    appt_data = item.get("appointment_data") or {}
    assert isinstance(appt_data, dict)
    assert "time_slot" not in appt_data, (
        f"date 模式订单的 appointment_data 必须被后端剥离 time_slot；实际={appt_data}"
    )


@pytest.mark.asyncio
async def test_tc3_time_slot_mode_create_order_with_full_data_succeeds(
    client: AsyncClient, admin_headers, auth_headers
):
    """time_slot 模式：完整传 date + time_slot → 200 OK；订单回传完整 appointment_data。"""
    pid = await _create_product(
        client, admin_headers,
        name="TimeSlotMode·Full商品",
        cat_name="CheckoutDateMode-Cat3",
        appointment_mode="time_slot",
    )
    appt_date = _future_date_iso(1)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{
                "product_id": pid,
                "quantity": 1,
                "appointment_time": f"{appt_date}T09:00:00",
                "appointment_data": {
                    "date": appt_date,
                    "time_slot": "09:00-10:00",
                },
            }],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, (
        f"time_slot 模式完整提交应当 200 OK；实际 status={resp.status_code} body={resp.text}"
    )
    order_id = resp.json()["id"]
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    item = detail.json()["items"][0]
    appt_data = item.get("appointment_data") or {}
    if isinstance(appt_data, dict):
        assert appt_data.get("date") == appt_date
        assert appt_data.get("time_slot") == "09:00-10:00"
    # 同时验证 appointment_mode 透传
    assert item.get("appointment_mode") == "time_slot"


@pytest.mark.asyncio
async def test_tc4_none_mode_create_order_without_appointment(
    client: AsyncClient, admin_headers, auth_headers
):
    """none 模式：不传任何预约信息 → 200 OK；订单也不应有 appointment_time / time_slot。"""
    pid = await _create_product(
        client, admin_headers,
        name="NoneMode·普通商品",
        cat_name="CheckoutDateMode-Cat4",
        appointment_mode="none",
        purchase_appt_mode="purchase_with_appointment",
    )
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, (
        f"none 模式商品下单应当 200 OK；实际 status={resp.status_code} body={resp.text}"
    )
    order_id = resp.json()["id"]
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    item = detail.json()["items"][0]
    assert not item.get("appointment_time")
    appt_data = item.get("appointment_data") or {}
    if isinstance(appt_data, dict):
        assert not appt_data.get("time_slot")


@pytest.mark.asyncio
async def test_tc5_order_detail_exposes_appointment_mode_for_date(
    client: AsyncClient, admin_headers, auth_headers
):
    """订单详情接口必须透传 OrderItem.appointment_mode='date'，前端据此屏蔽时段行。"""
    pid = await _create_product(
        client, admin_headers,
        name="DateMode·透传校验",
        cat_name="CheckoutDateMode-Cat5",
        appointment_mode="date",
    )
    appt_date = _future_date_iso(1)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{
                "product_id": pid,
                "quantity": 1,
                "appointment_time": f"{appt_date}T00:00:00",
                "appointment_data": {"date": appt_date},
            }],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    order_id = resp.json()["id"]
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.status_code == 200
    item = detail.json()["items"][0]
    assert item.get("appointment_mode") == "date", (
        f"订单详情必须透传 appointment_mode='date'，否则前端无法屏蔽时段行。实际 item={item}"
    )
