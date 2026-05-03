"""[先下单后预约] Bug 修复测试 — v1.0

覆盖场景：
- TC1: book_after_pay 商品下单不传 appointment_time → 创建成功
- TC2: book_after_pay 商品下单误传 appointment_time → 创建成功且后端忽略（DB 中为 NULL）
- TC3: 模拟付款 → 订单状态自动变为 pending_appointment
- TC4: 通过 /appointment 接口设置预约 → 订单流转到 appointed
- TC5: 对照组：purchase_with_appointment + 不传 appointment_time → 400 校验失败
- TC6: 对照组：purchase_with_appointment + 传 appointment_time → 创建成功（保持原逻辑）
"""

import pytest
from httpx import AsyncClient


async def _create_cat(client: AsyncClient, admin_headers, name="先下单后预约分类") -> int:
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
    purchase_appt_mode: str,
) -> int:
    cid = await _create_cat(client, admin_headers, cat_name)
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": name,
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 100.0,
            "sale_price": 99.0,
            "stock": 100,
            "status": "active",
            "images": ["https://example.com/test.jpg"],
            "appointment_mode": "date",
            "advance_days": 7,
            "include_today": True,
            "daily_quota": 50,
            "purchase_appointment_mode": purchase_appt_mode,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_book_after_pay_product(client: AsyncClient, admin_headers) -> int:
    return await _create_product(
        client,
        admin_headers,
        name="先下单后预约·体检套餐",
        cat_name="BookAfterPay分类",
        purchase_appt_mode="appointment_later",
    )


async def _create_book_with_order_product(client: AsyncClient, admin_headers) -> int:
    return await _create_product(
        client,
        admin_headers,
        name="下单即预约·体检套餐",
        cat_name="BookWithOrder分类",
        purchase_appt_mode="purchase_with_appointment",
    )


@pytest.mark.asyncio
async def test_tc1_book_after_pay_create_without_appointment_time(
    client: AsyncClient, admin_headers, auth_headers
):
    pid = await _create_book_after_pay_product(client, admin_headers)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] > 0
    assert body["items"][0]["appointment_time"] is None


@pytest.mark.asyncio
async def test_tc2_book_after_pay_ignores_misposted_appointment_time(
    client: AsyncClient, admin_headers, auth_headers
):
    pid = await _create_book_after_pay_product(client, admin_headers)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [
                {
                    "product_id": pid,
                    "quantity": 1,
                    "appointment_time": "2030-01-01T10:00:00",
                    "appointment_data": {
                        "date": "2030-01-01",
                        "time_slot": "10:00-11:00",
                    },
                }
            ],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 后端必须忽略前端误传值
    assert body["items"][0]["appointment_time"] is None
    assert body["items"][0]["appointment_data"] in (None, {}, [])


@pytest.mark.asyncio
async def test_tc3_pay_order_enters_pending_appointment(
    client: AsyncClient, admin_headers, auth_headers
):
    pid = await _create_book_after_pay_product(client, admin_headers)
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

    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "wechat"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 200, pay_resp.text
    assert pay_resp.json().get("status") in ("pending_appointment", "待预约")

    # 详情接口确认
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending_appointment"


@pytest.mark.asyncio
async def test_tc4_set_appointment_transitions_to_pending_use(
    client: AsyncClient, admin_headers, auth_headers
):
    """[PRD 订单状态机简化方案 v1.0] 用户首次填预约日：直接跳到 pending_use。"""
    pid = await _create_book_after_pay_product(client, admin_headers)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    order_id = resp.json()["id"]
    item_id = resp.json()["items"][0]["id"]

    await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "wechat"},
        headers=auth_headers,
    )

    # 用户在订单详情发起预约
    appt_resp = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={
            "item_id": item_id,
            "appointment_time": "2030-12-01T10:00:00",
            "appointment_data": {
                "date": "2030-12-01",
                "time_slot": "10:00-11:00",
            },
        },
        headers=auth_headers,
    )
    assert appt_resp.status_code == 200, appt_resp.text
    # 新状态机：首次填预约日直跳 pending_use
    assert appt_resp.json().get("status") == "pending_use"


@pytest.mark.asyncio
async def test_tc5_book_with_order_requires_appointment_time(
    client: AsyncClient, admin_headers, auth_headers
):
    pid = await _create_book_with_order_product(client, admin_headers)
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    # 对照组保持原校验：必填
    assert resp.status_code == 400, resp.text
    assert "预约时间" in resp.text or "appointment" in resp.text.lower()


@pytest.mark.asyncio
async def test_tc6_book_with_order_with_appointment_time_ok(
    client: AsyncClient, admin_headers, auth_headers
):
    pid = await _create_book_with_order_product(client, admin_headers)
    from datetime import datetime, timedelta
    appt_dt = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    appt_str = appt_dt.strftime("%Y-%m-%dT%H:%M:%S")
    appt_date = appt_dt.strftime("%Y-%m-%d")
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [
                {
                    "product_id": pid,
                    "quantity": 1,
                    "appointment_time": appt_str,
                    "appointment_data": {
                        "date": appt_date,
                        "time_slot": "10:00-11:00",
                    },
                }
            ],
            "payment_method": "wechat",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["appointment_time"] is not None
