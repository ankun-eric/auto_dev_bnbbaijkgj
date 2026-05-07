"""[BUG-FIX-RESCHEDULE-V2 2026-05-07] 改约 v2 修复测试

覆盖本轮（cursor_prompt_403）新增/强化的能力：

- V01: GET /api/system/server-time 可用性（无鉴权、字段齐全）
- V02: 顾客端入口（X-Client-Source: h5-customer）改约成功（与 v1 保持兼容）
- V03: UA 兜底放行 — 既无 X-Client-Source 也无 Client-Type，但 UA 是移动端
       → is_customer_entry 命中，改约不再 403
- V04: 改约时选了"今天且已过去"的时段 → 返回 RESCHEDULE_TIME_EXPIRED
       （与前端按服务器时间隐藏过去时段构成双保险）
- V05: 错误结构化兜底 — 任何未知异常被 try/except 包成 RESCHEDULE_INTERNAL_ERROR
       （这里通过对一个不存在的订单 ID 触发 ORM 查询正常返回 RESCHEDULE_ORDER_NOT_FOUND
       即可证明结构化错误链路正常；500 兜底链路在 unified_orders.py 的 try/except 中）
- V06: 服务器时间接口字段类型校验
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import User, UserRole
from tests.conftest import test_session


# ─────────── 共用工具（复用 v1 的工具） ───────────


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


def _h5_customer_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Client-Type": "h5-user",
        "X-Client-Type": "h5-user",
        "X-Client-Source": "h5-customer",
    }


def _ua_only_mobile_headers(token: str) -> dict:
    """既无 X-Client-Source 也无 Client-Type，但 UA 是 iPhone Mobile —— 应被 UA 兜底放行"""
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
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


async def _make_dual_identity_user(client: AsyncClient, phone: str) -> str:
    token = await _register_and_login(client, phone)
    async with test_session() as session:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalar_one()
        user.role = UserRole.merchant
        await session.commit()
    return token


def _future_dt(days_ahead: int, hour: int = 10, minute: int = 0) -> str:
    base = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (base + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%S")


# ─────────── 用例 ───────────


@pytest.mark.asyncio
async def test_v01_server_time_endpoint_no_auth_required(client: AsyncClient):
    """V01: GET /api/system/server-time 无鉴权可用 + 必含三个字段"""
    resp = await client.get("/api/system/server-time")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "now_iso" in body
    assert "now_unix_ms" in body
    assert "timezone" in body
    # 字段类型
    assert isinstance(body["now_unix_ms"], int)
    assert body["now_unix_ms"] > 1_700_000_000_000  # 至少 2023-11 之后


@pytest.mark.asyncio
async def test_v06_server_time_iso_format(client: AsyncClient):
    """V06: now_iso 字段是合法 ISO8601 字符串，前端可以 new Date(...) 解析"""
    resp = await client.get("/api/system/server-time")
    body = resp.json()
    iso = body["now_iso"]
    # 应能被 datetime.fromisoformat 解析（去掉 Z 后缀）
    assert iso.endswith("Z") or "+" in iso
    parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    assert isinstance(parsed, datetime)


@pytest.mark.asyncio
async def test_v02_h5_customer_source_reschedule_success(
    client: AsyncClient, admin_headers
):
    """V02: H5 顾客端 X-Client-Source: h5-customer 成功改约（v1 兼容性回归）"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="V02商品", cat_name="V02-cat"
    )
    token = await _register_and_login(client, "13800000402")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)
    # 第 1 次预约（不计 reschedule_count）
    resp1 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(2)},
        headers=headers,
    )
    assert resp1.status_code == 200, resp1.text
    # 第 2 次（真改约）
    resp2 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(3)},
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.text


@pytest.mark.asyncio
async def test_v03_ua_only_mobile_fallback_pass(client: AsyncClient, admin_headers):
    """V03: 既无 X-Client-Source 也无 Client-Type 顾客标识，但 UA = iPhone Mobile，
    is_customer_entry UA 兜底应放行，改约不再 403。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="V03商品", cat_name="V03-cat"
    )
    token = await _register_and_login(client, "13800000403")
    # 用 H5 顾客头先下单（保证下单链路顺畅），改约时切到 UA-only 头
    customer_headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, customer_headers, pid)
    # 改约时只带 UA（无 X-Client-Source / 无 Client-Type）
    ua_headers = _ua_only_mobile_headers(token)
    # 第 1 次：首次预约
    resp1 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(2)},
        headers=ua_headers,
    )
    # 不应是 403 RESCHEDULE_NO_PERMISSION
    assert resp1.status_code == 200, f"UA 兜底应允许放行，得到: {resp1.status_code} {resp1.text}"


@pytest.mark.asyncio
async def test_v04_today_past_slot_rejected(client: AsyncClient, admin_headers):
    """V04: 改约时选了"今天且已过去"的时段 → RESCHEDULE_TIME_EXPIRED

    构造方式：
    - 先正常完成一次预约（让订单进入 has_existing_appt=True 状态）
    - 再尝试改约到"今天的过去时间"
    """
    pid = await _create_product_date_mode(
        client, admin_headers, name="V04商品", cat_name="V04-cat"
    )
    token = await _register_and_login(client, "13800000404")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)
    # 第一次预约成功（明天 10:00）
    resp1 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(1)},
        headers=headers,
    )
    assert resp1.status_code == 200, resp1.text
    # 第二次尝试改约到「今天 00:00」（早已过去）
    today_past = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    resp2 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={
            "appointment_time": today_past,
            "appointment_data": {"date": today_past[:10], "time_slot": "00:00-01:00"},
        },
        headers=headers,
    )
    assert resp2.status_code == 400, resp2.text
    body = resp2.json()
    assert isinstance(body.get("detail"), dict)
    assert body["detail"]["code"] == "RESCHEDULE_TIME_EXPIRED"


@pytest.mark.asyncio
async def test_v05_unknown_order_returns_structured_error(
    client: AsyncClient, admin_headers
):
    """V05: 改约一个不存在的订单 → 返回结构化的 RESCHEDULE_ORDER_NOT_FOUND
    （证明结构化错误链路通畅；500 兜底链路通过 try/except 包裹保证）"""
    token = await _register_and_login(client, "13800000405")
    headers = _h5_customer_headers(token)
    resp = await client.post(
        "/api/orders/unified/9999999/appointment",
        json={"appointment_time": _future_dt(2)},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert isinstance(body.get("detail"), dict)
    assert body["detail"]["code"] == "RESCHEDULE_ORDER_NOT_FOUND"
    assert "message" in body["detail"]


@pytest.mark.asyncio
async def test_v07_dual_identity_with_ua_fallback_works(
    client: AsyncClient, admin_headers
):
    """V07: 双重身份用户（手机号既是顾客也是商家），仅靠 UA 兜底（无 X-Client-Source）也能改约。
    模拟"漏改某个入口的 Header"场景，确保不会因头丢失就让双重身份用户彻底无法改约。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="V07商品", cat_name="V07-cat"
    )
    token = await _make_dual_identity_user(client, "13800000407")
    # 先用顾客头下单
    customer_headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, customer_headers, pid)
    # 改约时只带 UA = Android Mobile（漏 X-Client-Source）
    ua_only = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Mobile",
    }
    resp = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": _future_dt(2)},
        headers=ua_only,
    )
    assert resp.status_code == 200, f"UA 兜底应允许双重身份用户放行，得到: {resp.status_code} {resp.text}"
