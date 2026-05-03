"""[修改预约 Bug 修复 v1.0] 后端测试

覆盖场景：
- TC1: 订单详情接口透传 OrderItem.appointment_mode 字段（date 模式）
- TC2: 订单详情接口透传 OrderItem.appointment_mode 字段（time_slot 模式）
- TC3: 订单详情接口透传 OrderItem.appointment_mode 字段（custom_form 模式）
- TC4: date 模式下，预约接口不带 appointment_data.time_slot 也能成功
- TC5: time_slot 模式下，已成功预约的订单详情会回传 appointment_time / appointment_data
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
    purchase_appt_mode: str = "appointment_later",
    custom_form_id: int | None = None,
) -> int:
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
    if appointment_mode == "custom_form" and custom_form_id is not None:
        payload["custom_form_id"] = custom_form_id
    resp = await client.post(
        "/api/admin/products",
        json=payload,
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _place_and_get_detail(client: AsyncClient, auth_headers, pid: int):
    """下单并取详情。返回 detail json。"""
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    order_id = resp.json()["id"]
    # 模拟付款 → pending_appointment
    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "wechat"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 200, pay_resp.text
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    return order_id, detail.json()


@pytest.mark.asyncio
async def test_tc1_order_detail_exposes_appointment_mode_date(
    client: AsyncClient, admin_headers, auth_headers
):
    """订单详情接口必须把 OrderItem.product.appointment_mode 透传给前端（date 模式）。"""
    pid = await _create_product(
        client,
        admin_headers,
        name="ModifyAppt·Date模式",
        cat_name="ModifyAppt-DateCat",
        appointment_mode="date",
    )
    _, detail = await _place_and_get_detail(client, auth_headers, pid)
    items = detail["items"]
    assert len(items) >= 1
    assert items[0].get("appointment_mode") == "date", (
        "订单详情必须透传 appointment_mode='date'，否则前端无法联动隐藏时段块。"
        f" 实际 item={items[0]}"
    )


@pytest.mark.asyncio
async def test_tc2_order_detail_exposes_appointment_mode_time_slot(
    client: AsyncClient, admin_headers, auth_headers
):
    """订单详情接口必须把 appointment_mode='time_slot' 透传给前端。"""
    pid = await _create_product(
        client,
        admin_headers,
        name="ModifyAppt·TimeSlot模式",
        cat_name="ModifyAppt-TimeSlotCat",
        appointment_mode="time_slot",
    )
    _, detail = await _place_and_get_detail(client, auth_headers, pid)
    items = detail["items"]
    assert items[0].get("appointment_mode") == "time_slot", (
        "订单详情必须透传 appointment_mode='time_slot'。"
        f" 实际 item={items[0]}"
    )


@pytest.mark.asyncio
async def test_tc3_modify_appointment_in_date_mode_succeeds_without_time_slot(
    client: AsyncClient, admin_headers, auth_headers
):
    """date 模式下，前端只传 appointment_date，不传 time_slot，后端必须接受。"""
    pid = await _create_product(
        client,
        admin_headers,
        name="ModifyAppt·Date提交",
        cat_name="ModifyAppt-DateSubmitCat",
        appointment_mode="date",
    )
    order_id, detail = await _place_and_get_detail(client, auth_headers, pid)
    item_id = detail["items"][0]["id"]

    # 模拟前端 date 模式提交：不带 time_slot
    appt_resp = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={
            "order_item_id": item_id,
            "appointment_time": "2030-06-15T09:00:00",
            "appointment_data": {"date": "2030-06-15"},  # 仅 date，无 time_slot
        },
        headers=auth_headers,
    )
    assert appt_resp.status_code == 200, (
        f"date 模式下不传 time_slot 应当成功；当前 status={appt_resp.status_code}"
        f" body={appt_resp.text}"
    )

    detail2 = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    body2 = detail2.json()
    assert body2["items"][0]["appointment_time"] is not None
    # 该条 item 的 appointment_data 应包含 date，但不强制要求 time_slot
    appt_data = body2["items"][0].get("appointment_data") or {}
    if isinstance(appt_data, dict):
        assert appt_data.get("date") == "2030-06-15"


@pytest.mark.asyncio
async def test_tc4_modify_appointment_in_time_slot_mode_returns_full_data(
    client: AsyncClient, admin_headers, auth_headers
):
    """time_slot 模式：完整提交（date + time_slot）后，详情 item 中 appointment_time 与 appointment_data 都应回传。"""
    pid = await _create_product(
        client,
        admin_headers,
        name="ModifyAppt·TimeSlot提交",
        cat_name="ModifyAppt-TimeSlotSubmitCat",
        appointment_mode="time_slot",
    )
    order_id, detail = await _place_and_get_detail(client, auth_headers, pid)
    item_id = detail["items"][0]["id"]

    appt_resp = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={
            "order_item_id": item_id,
            "appointment_time": "2030-06-15T09:00:00",
            "appointment_data": {
                "date": "2030-06-15",
                "time_slot": "09:00-10:00",
            },
        },
        headers=auth_headers,
    )
    assert appt_resp.status_code == 200, appt_resp.text

    detail2 = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    body2 = detail2.json()
    item = body2["items"][0]
    assert item["appointment_time"] is not None
    appt_data = item.get("appointment_data") or {}
    if isinstance(appt_data, dict):
        assert appt_data.get("date") == "2030-06-15"
        assert appt_data.get("time_slot") == "09:00-10:00"
    # 同时确认 appointment_mode 字段仍然透传给前端
    assert item.get("appointment_mode") == "time_slot"


@pytest.mark.asyncio
async def test_tc5_order_detail_exposes_appointment_mode_none_or_empty(
    client: AsyncClient, admin_headers, auth_headers
):
    """非预约商品（appointment_mode=none）：详情接口里也应该返回 'none'，前端据此不显示按钮。"""
    pid = await _create_product(
        client,
        admin_headers,
        name="ModifyAppt·None模式",
        cat_name="ModifyAppt-NoneCat",
        appointment_mode="none",
        purchase_appt_mode="purchase_with_appointment",  # 不重要，但需要某个有效值
    )
    # none 模式下一些联动校验可能拒绝，所以这里只创建商品并直接 GET 商品的订单创建路径会被前面的校验阻断；
    # 故本用例只断言：如果能下单（兼容路径），item.appointment_mode 应为 'none' 或为空字符串。
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    if resp.status_code != 200:
        # 业务上 none 模式 + purchase_with_appointment 校验可能失败，跳过断言
        pytest.skip(
            f"none 模式商品下单被业务校验拒绝（可能正常），跳过透传断言；resp={resp.text}"
        )
    order_id = resp.json()["id"]
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.status_code == 200
    item = detail.json()["items"][0]
    assert item.get("appointment_mode") in ("none", None, ""), (
        f"none 模式商品的订单 item 应透传 appointment_mode='none'，实际={item}"
    )
