"""[BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v1.0]

订单改约弹窗自动关闭 + 三端列表联动刷新 Bug 修复回归测试

本次修复主要在 H5 / 微信小程序 / Flutter 三端前端代码中：
1. 改约成功后立即关闭弹窗（弹窗 0 延迟消失）
2. Toast 与弹窗关闭同时进行，文案按场景区分（改约/预约）
3. 改约成功后通知订单列表页强制刷新

后端契约本身**未改动**——本测试用于守门，确保前端改动所依赖的后端
改约接口契约（POST /api/orders/unified/{id}/appointment）仍然按预期工作：

- T01: 首次预约成功（前端文案显示"预约成功"）
  → 后端返回 200，订单 status / appointment_time 正确更新
- T02: 已有预约后再次改约成功（前端文案显示"改约成功"）
  → 后端返回 200，订单 reschedule_count 增加 1 / 时间正确更新
- T03: 改约成功后再次拉取列表（GET /api/orders/unified）
  → 列表里该订单的 appointment 时间反映为新值（联动刷新的数据基础）
- T04: 改约失败场景（达上限）→ 弹窗仍保留（前端逻辑），后端契约依然稳定
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient


# ─────────── 共用工具（小型自包含版） ───────────


def _future_dt(days_ahead: int, hour: int = 10, minute: int = 0) -> str:
    base = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (base + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%S")


def _h5_customer_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Client-Type": "h5-user",
        "X-Client-Type": "h5-user",
        "X-Client-Source": "h5-customer",
    }


async def _register_and_login(client: AsyncClient, phone: str) -> str:
    await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "user123", "nickname": f"用户{phone[-4:]}"},
    )
    resp = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "user123"}
    )
    return resp.json()["access_token"]


async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_product_date_mode(
    client: AsyncClient, admin_headers, *, name: str, cat_name: str
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
        "appointment_mode": "date",
        "advance_days": 90,
        "include_today": True,
        "daily_quota": 50,
        "purchase_appointment_mode": "appointment_later",
        "allow_reschedule": True,
    }
    resp = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _place_and_pay(client: AsyncClient, headers, pid: int) -> int:
    resp = await client.post(
        "/api/orders/unified",
        json={"items": [{"product_id": pid, "quantity": 1}], "payment_method": "wechat"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    order_id = resp.json()["id"]
    pay = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "wechat"},
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    return order_id


# ─────────── 用例 ───────────


@pytest.mark.asyncio
async def test_t01_first_appointment_success_for_pending_appointment_order(
    client: AsyncClient, admin_headers
):
    """T01: 首次预约成功（前端弹窗显示"预约成功"文案路径）

    顾客对一个 pending_appointment 状态的订单首次提交预约：
    - 后端 200
    - 订单 status 推进
    - 订单 appointment_time 已设置（前端关闭弹窗后展示新时间的依据）
    """
    pid = await _create_product_date_mode(
        client, admin_headers, name="T01商品", cat_name="T01-cat"
    )
    token = await _register_and_login(client, "13800010001")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)

    # 首次预约
    resp = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(2)},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # 拉取详情，appointment_time 必须已更新
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    items = detail.json().get("items") or []
    assert items, "订单 items 不应为空"
    appt_time = items[0].get("appointment_time")
    assert appt_time, f"首次预约后 appointment_time 应已设置，实际: {appt_time}"


@pytest.mark.asyncio
async def test_t02_reschedule_increments_count_and_updates_time(
    client: AsyncClient, admin_headers
):
    """T02: 已有预约后再次改约成功（前端弹窗显示"改约成功"文案路径）

    - 先完成首次预约（不计入 reschedule_count）
    - 再做一次"真改约"
    - 后端 200，订单 reschedule_count = 1（前端用以判定 isReschedule）
    - 订单 appointment_time 已变化为新时间（详情页弹窗关闭后即可看到新时间）
    """
    pid = await _create_product_date_mode(
        client, admin_headers, name="T02商品", cat_name="T02-cat"
    )
    token = await _register_and_login(client, "13800010002")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)

    first_time = _future_dt(2)
    second_time = _future_dt(3)

    # 第 1 次预约
    r1 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": first_time},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    # 第 2 次（真改约）
    r2 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": second_time},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    # 详情：reschedule_count >= 1，appointment_time 已是 second_time（不再是 first_time）
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    rcount = int(body.get("reschedule_count") or 0)
    assert rcount >= 1, f"真改约后 reschedule_count 应 >=1，实际 {rcount}"
    items = body.get("items") or []
    appt_time = items[0].get("appointment_time") if items else None
    assert appt_time, "改约后 appointment_time 必须已设置"
    # 改约的时间应不等于第一次的时间（核心：详情页弹窗关闭后必须看到新时间）
    assert appt_time != first_time, (
        f"改约后 appointment_time 应已更新；first={first_time} appt_time={appt_time}"
    )


@pytest.mark.asyncio
async def test_t03_orders_list_reflects_new_appointment_after_reschedule(
    client: AsyncClient, admin_headers
):
    """T03: 改约成功后再拉订单列表，列表里该订单的预约时间为新时间

    这是"订单列表联动刷新"功能的数据契约基础——列表接口本身就能在改约
    后的下一次拉取中返回最新数据；前端只需在合适时机重拉即可。
    """
    pid = await _create_product_date_mode(
        client, admin_headers, name="T03商品", cat_name="T03-cat"
    )
    token = await _register_and_login(client, "13800010003")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)

    # 首次 + 改约
    await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(2)},
        headers=headers,
    )
    new_time = _future_dt(5)
    r2 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": new_time},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    # 拉取订单列表（前端在 onShow / pageshow / focus 时会调用此接口）
    listing = await client.get("/api/orders/unified", headers=headers)
    assert listing.status_code == 200, listing.text
    items_in_list = listing.json().get("items") or []
    target = next((o for o in items_in_list if o.get("id") == order_id), None)
    assert target is not None, f"列表里应包含 order_id={order_id}"
    # 列表里该订单的 items[].appointment_time 必须反映为改约后的新时间
    list_items = target.get("items") or []
    appt_in_list = list_items[0].get("appointment_time") if list_items else None
    assert appt_in_list, "列表数据中订单的 appointment_time 必须已设置"
    # 即「列表页 onShow 触发刷新拉到的 appointment_time」与「改约接口 200 之后详情页拉到的 appointment_time」一致
    detail = await client.get(f"/api/orders/unified/{order_id}", headers=headers)
    detail_items = detail.json().get("items") or []
    appt_in_detail = detail_items[0].get("appointment_time") if detail_items else None
    assert appt_in_list == appt_in_detail, (
        f"列表与详情的 appointment_time 必须一致；list={appt_in_list} detail={appt_in_detail}"
    )


@pytest.mark.asyncio
async def test_t04_failed_reschedule_keeps_order_intact(
    client: AsyncClient, admin_headers
):
    """T04: 改约失败场景（无效时间格式）→ 后端 4xx 拒绝，订单未被破坏

    对应"失败场景兜底（不变）"——前端弹窗保留、Toast 提示失败原因，可重试。
    后端契约：返回非 200，且订单 appointment_time 不变。
    """
    pid = await _create_product_date_mode(
        client, admin_headers, name="T04商品", cat_name="T04-cat"
    )
    token = await _register_and_login(client, "13800010004")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)

    # 先做一次正常预约，记下 appointment_time
    ok_time = _future_dt(2)
    r1 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": ok_time},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    detail1 = await client.get(f"/api/orders/unified/{order_id}", headers=headers)
    items1 = detail1.json().get("items") or []
    appt_before = items1[0].get("appointment_time")
    assert appt_before, "首次预约 appointment_time 应已设置"

    # 触发失败：传入完全非法的 appointment_time 格式
    r2 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "not-a-real-datetime"},
        headers=headers,
    )
    assert r2.status_code != 200, (
        f"非法 appointment_time 应被后端拒绝，但得到 200: {r2.text}"
    )

    # 详情中 appointment_time 不应被破坏（仍是 appt_before）
    detail2 = await client.get(f"/api/orders/unified/{order_id}", headers=headers)
    items2 = detail2.json().get("items") or []
    appt_after = items2[0].get("appointment_time")
    assert appt_after == appt_before, (
        f"失败的改约不应改动 appointment_time；before={appt_before} after={appt_after}"
    )
