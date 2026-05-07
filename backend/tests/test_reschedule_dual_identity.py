"""[双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0] 后端 pytest 测试

覆盖修复方案文档（BUG-FIX-RESCHEDULE-DUAL-IDENTITY-V1）的核心用例：

- T01: 双重身份用户在 H5 顾客端对自己手机号下的订单首次改约 → 改约成功
- T02: 双重身份用户在 H5 顾客端对自己订单连续改约 5 次以上 → 每次都成功（不卡次数）
- T03: 纯顾客身份改约 → 保持原有顾客逻辑（受改约次数限制）
- T05: H5 顾客端改约时所选时段已过期（过去时间）→ 返回结构化 RESCHEDULE_TIME_EXPIRED
- T06: H5 顾客端改约时所选时段超出 90 天范围 → 返回 RESCHEDULE_TIME_OUT_OF_RANGE
- T07: 纯顾客达到改约次数上限 → 返回 RESCHEDULE_LIMIT_EXCEEDED
- T08: 顾客尝试改他人订单 → 返回 RESCHEDULE_ORDER_NOT_FOUND（不会因为修复被放行）
- T09: 错误结构验证：所有失败响应必须含 code/message 字段（不再是单纯 "预约失败"）
- T_MINIPROGRAM_SOURCE: X-Client-Source: miniprogram-customer 也允许
- T_FLUTTER_SOURCE: X-Client-Source: flutter-customer 也允许
- T_NO_SOURCE_NO_TYPE: 既无 X-Client-Source 也无 Client-Type 顾客标识 → 403
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.models import User, UserRole
from tests.conftest import test_session


# ─────────── 共用工具 ───────────


async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_product_date_mode(
    client: AsyncClient,
    admin_headers,
    *,
    name: str,
    cat_name: str,
    reschedule_limit: int = 3,
) -> int:
    """创建一个 date 模式的可改约商品（避免触碰时段容量校验，专注本次 Bug）。"""
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
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    order_id = resp.json()["id"]
    pay_resp = await client.post(
        f"/api/orders/unified/{order_id}/pay",
        json={"payment_method": "wechat"},
        headers=headers,
    )
    assert pay_resp.status_code == 200, pay_resp.text
    return order_id


def _h5_customer_headers(token: str) -> dict:
    """H5 顾客端入口标识：X-Client-Source: h5-customer + Client-Type: h5-user。"""
    return {
        "Authorization": f"Bearer {token}",
        "Client-Type": "h5-user",
        "X-Client-Type": "h5-user",
        "X-Client-Source": "h5-customer",
    }


def _miniprogram_customer_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Client-Type": "miniprogram-user",
        "X-Client-Type": "miniprogram-user",
        "X-Client-Source": "miniprogram-customer",
    }


def _flutter_customer_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Client-Type": "app-user",
        "X-Client-Type": "app-user",
        "X-Client-Source": "flutter-customer",
    }


def _no_customer_headers(token: str) -> dict:
    """模拟未携带任何顾客标识（既无 X-Client-Source 也无顾客 Client-Type）。
    用 PC 端 UA 兜底，避免被 UA 识别为 h5-mobile 或 verify-miniprogram。"""
    return {
        "Authorization": f"Bearer {token}",
        "Client-Type": "pc-web",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }


async def _register_and_login(
    client: AsyncClient, phone: str, password: str = "user123"
) -> str:
    await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": password, "nickname": f"用户{phone[-4:]}"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": password},
    )
    return resp.json()["access_token"]


async def _make_dual_identity_user(client: AsyncClient, phone: str) -> str:
    """创建一个"双重身份用户"——同时具备商家身份的用户，并返回其登录 token。

    通过把数据库中该用户的 role 直接改为 merchant 来模拟"同一手机号既是顾客又是商家"，
    这正是本次 Bug 描述的双重身份语义。
    """
    token = await _register_and_login(client, phone)
    async with test_session() as session:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalar_one()
        user.role = UserRole.merchant
        await session.commit()
    return token


# ─────────── 用例 ───────────


@pytest.mark.asyncio
async def test_t01_dual_identity_first_reschedule_succeeds(
    client: AsyncClient, admin_headers
):
    """T01: 双重身份用户在 H5 顾客端对自己订单首次改约（已有过预约时间），应成功。"""
    pid = await _create_product_date_mode(
        client,
        admin_headers,
        name="改约商品T01",
        cat_name="改约-DualT01",
    )
    token = await _make_dual_identity_user(client, "13911110001")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)

    # 第 1 次：首次设置预约（不计入改约次数）
    r1 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    # 第 2 次：真正的"改约"
    r2 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-16T10:00:00"},
        headers=headers,
    )
    assert r2.status_code == 200, (
        "双重身份用户从 H5 顾客端入口改约必须成功，"
        f"当前 status={r2.status_code} body={r2.text}"
    )
    body = r2.json()
    assert body.get("status") == "pending_use"
    assert int(body.get("reschedule_count", 0)) >= 1


@pytest.mark.asyncio
async def test_t02_dual_identity_unlimited_reschedule(
    client: AsyncClient, admin_headers
):
    """T02: 双重身份用户从 H5 顾客端入口连续改约 5 次以上，每次都成功（不卡上限）。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T02", cat_name="改约-DualT02"
    )
    token = await _make_dual_identity_user(client, "13911110002")
    headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)

    # 首次预约
    r0 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    assert r0.status_code == 200

    # 连续改约 6 次（远超默认 reschedule_limit=3）
    for i in range(6):
        r = await client.post(
            f"/api/orders/unified/{order_id}/appointment",
            json={"appointment_time": f"2030-06-{16 + i:02d}T10:00:00"},
            headers=headers,
        )
        assert r.status_code == 200, (
            f"商家身份从顾客端入口改约第 {i + 1} 次应仍然成功，"
            f"当前 status={r.status_code} body={r.text}"
        )


@pytest.mark.asyncio
async def test_t03_pure_customer_keeps_original_logic(
    client: AsyncClient, admin_headers, auth_headers
):
    """T03: 纯顾客身份（手机号不在商家表）改约 → 受默认 reschedule_limit=3 限制。
    本用例验证修复**不破坏纯顾客侧的原有规则**。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T03", cat_name="改约-PureT03"
    )
    # auth_headers 默认带 Client-Type: h5-user，本用例追加 X-Client-Source 模拟新版客户端
    headers = dict(auth_headers)
    headers["X-Client-Source"] = "h5-customer"
    order_id = await _place_and_pay(client, headers, pid)

    # 首次预约
    await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    # 改约 3 次
    for i in range(3):
        r = await client.post(
            f"/api/orders/unified/{order_id}/appointment",
            json={"appointment_time": f"2030-06-{16 + i:02d}T10:00:00"},
            headers=headers,
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_t05_time_expired_returns_structured_code(
    client: AsyncClient, admin_headers, auth_headers
):
    """T05: 改约时所选时段已过期（过去时间） → 返回 code=RESCHEDULE_TIME_EXPIRED。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T05", cat_name="改约-T05"
    )
    headers = dict(auth_headers)
    headers["X-Client-Source"] = "h5-customer"
    order_id = await _place_and_pay(client, headers, pid)

    # 首次预约（合法时间）
    await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    # 改约到一个过去的时间（2020 年）
    r = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2020-01-01T10:00:00"},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    body = r.json()
    detail = body.get("detail")
    assert isinstance(detail, dict), f"必须返回结构化错误: {body}"
    assert detail.get("code") == "RESCHEDULE_TIME_EXPIRED", body
    # message 必须不是空、不是"预约失败"
    assert detail.get("message"), body
    assert detail.get("message") != "预约失败"


@pytest.mark.asyncio
async def test_t06_time_out_of_range_returns_structured_code(
    client: AsyncClient, admin_headers, auth_headers
):
    """T06: 改约日期超出 90 天 → 返回 code=RESCHEDULE_TIME_OUT_OF_RANGE。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T06", cat_name="改约-T06"
    )
    headers = dict(auth_headers)
    headers["X-Client-Source"] = "h5-customer"
    order_id = await _place_and_pay(client, headers, pid)
    await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    r = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2099-01-01T10:00:00"},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "RESCHEDULE_TIME_OUT_OF_RANGE"


@pytest.mark.asyncio
async def test_t07_pure_customer_limit_exceeded_returns_structured_code(
    client: AsyncClient, admin_headers, auth_headers
):
    """T07: 纯顾客达到 reschedule_limit=3 后，第 4 次改约返回 RESCHEDULE_LIMIT_EXCEEDED。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T07", cat_name="改约-T07"
    )
    headers = dict(auth_headers)
    headers["X-Client-Source"] = "h5-customer"
    order_id = await _place_and_pay(client, headers, pid)

    # 首次预约
    await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    # 改约 3 次（消耗到上限）
    for i in range(3):
        r = await client.post(
            f"/api/orders/unified/{order_id}/appointment",
            json={"appointment_time": f"2030-06-{16 + i:02d}T10:00:00"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
    # 第 4 次必须被拦截
    r4 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-20T10:00:00"},
        headers=headers,
    )
    assert r4.status_code == 400
    detail = r4.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "RESCHEDULE_LIMIT_EXCEEDED"
    assert detail.get("message") != "预约失败"


@pytest.mark.asyncio
async def test_t08_cannot_reschedule_others_order(
    client: AsyncClient, admin_headers, auth_headers
):
    """T08: 顾客尝试改约别人订单 → 返回 RESCHEDULE_ORDER_NOT_FOUND（不会被修复放行）。

    这是关键守门用例，验证修复未引入"商家越权改别人订单"风险。
    """
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T08", cat_name="改约-T08"
    )
    # 用户 A（双重身份）下单
    token_a = await _make_dual_identity_user(client, "13911110008")
    headers_a = _h5_customer_headers(token_a)
    order_id_a = await _place_and_pay(client, headers_a, pid)

    # 用户 B（普通顾客）尝试改约 A 的订单
    headers_b = dict(auth_headers)  # auth_headers 是 13900000001
    headers_b["X-Client-Source"] = "h5-customer"
    r = await client.post(
        f"/api/orders/unified/{order_id_a}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers_b,
    )
    assert r.status_code in (404, 403), r.text
    detail = r.json().get("detail")
    if r.status_code == 404:
        assert isinstance(detail, dict)
        assert detail.get("code") == "RESCHEDULE_ORDER_NOT_FOUND"


@pytest.mark.asyncio
async def test_t_miniprogram_source_allows_dual_identity(
    client: AsyncClient, admin_headers
):
    """X-Client-Source: miniprogram-customer 同样应放行双重身份用户的改约。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品MP", cat_name="改约-MP"
    )
    token = await _make_dual_identity_user(client, "13911110011")
    headers = _miniprogram_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)
    r0 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    assert r0.status_code == 200, r0.text


@pytest.mark.asyncio
async def test_t_flutter_source_allows_dual_identity(
    client: AsyncClient, admin_headers
):
    """X-Client-Source: flutter-customer 同样应放行双重身份用户的改约。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品FL", cat_name="改约-FL"
    )
    token = await _make_dual_identity_user(client, "13911110012")
    headers = _flutter_customer_headers(token)
    order_id = await _place_and_pay(client, headers, pid)
    r0 = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=headers,
    )
    assert r0.status_code == 200, r0.text


@pytest.mark.asyncio
async def test_t_no_customer_source_rejected(client: AsyncClient, admin_headers):
    """既无 X-Client-Source 也无顾客 Client-Type，PC UA 兜底 → 必须返回 403 (RESCHEDULE_NO_PERMISSION)。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品NS", cat_name="改约-NS"
    )
    # 顾客先在合法入口下单 + 首次预约
    token = await _register_and_login(client, "13911110013")
    legal_headers = _h5_customer_headers(token)
    order_id = await _place_and_pay(client, legal_headers, pid)

    # 然后用"无顾客标识"的 headers 尝试改约
    bad_headers = _no_customer_headers(token)
    r = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2030-06-15T09:00:00"},
        headers=bad_headers,
    )
    assert r.status_code == 403, r.text
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "RESCHEDULE_NO_PERMISSION"


@pytest.mark.asyncio
async def test_t09_all_errors_are_structured(
    client: AsyncClient, admin_headers, auth_headers
):
    """无论失败原因为何，detail 都应是 {code, message, detail} 结构，
    保证前端能稳定解析 code/message，不再统一兜底"预约失败"。"""
    pid = await _create_product_date_mode(
        client, admin_headers, name="改约商品T09", cat_name="改约-T09"
    )
    headers = dict(auth_headers)
    headers["X-Client-Source"] = "h5-customer"
    order_id = await _place_and_pay(client, headers, pid)

    # 触发"过期时间"错误
    r = await client.post(
        f"/api/orders/unified/{order_id}/appointment",
        json={"appointment_time": "2020-01-01T10:00:00"},
        headers=headers,
    )
    assert r.status_code >= 400
    body = r.json()
    detail = body.get("detail")
    assert isinstance(detail, dict), f"detail 必须是 dict 结构，实际: {body}"
    for required_field in ("code", "message"):
        assert required_field in detail, f"缺失字段 {required_field}: {detail}"
    assert isinstance(detail["code"], str) and detail["code"].startswith("RESCHEDULE_")
    assert isinstance(detail["message"], str) and detail["message"]
    assert detail["message"] != "预约失败", "message 必须是具体业务文案，不是兜底"
