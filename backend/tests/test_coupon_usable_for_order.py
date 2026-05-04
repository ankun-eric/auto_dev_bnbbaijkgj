"""[优惠券下单页 Bug 修复 v2] 后端测试

覆盖 4 个 Bug 中后端可测的部分：

- B1: 免费试用券下单——0 元抵扣，不要求 condition_amount，应付金额 0
- B3-NEW: 下单页券列表新接口 /api/coupons/usable-for-order：
        ① 不属于本商品适用范围的券不出现
        ② 已过期的券不出现
        ③ 已下架的券不出现
        ④ 满足门槛的满减券出现，不满足的不出现
        ⑤ free_trial 强制忽略 condition_amount
- 创单兜底（B3 后端兜底）：用户篡改 coupon_id 提交不适用的券，应返回 422

约 6 个 pytest-asyncio 用例，覆盖核心业务路径。
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select


async def _create_cat(client: AsyncClient, admin_headers, name: str) -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_product(
    client: AsyncClient, admin_headers, *, name: str, cat_name: str, sale_price: float = 100.0
) -> int:
    cid = await _create_cat(client, admin_headers, cat_name)
    payload = {
        "name": name,
        "category_id": cid,
        "fulfillment_type": "in_store",
        "original_price": sale_price + 1,
        "sale_price": sale_price,
        "stock": 100,
        "status": "active",
        "images": ["https://example.com/test.jpg"],
        "appointment_mode": "none",
        "purchase_appointment_mode": "purchase_with_appointment",
    }
    resp = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_and_grant_coupon(
    client: AsyncClient, admin_headers, auth_headers, *,
    name: str,
    type: str = "voucher",
    condition_amount: float = 0,
    discount_value: float = 10,
    discount_rate: float = 1.0,
    scope: str = "all",
    scope_ids=None,
    validity_days: int = 30,
    grant_to_self: bool = True,
) -> tuple[int, int | None]:
    """创建优惠券并（可选）发到当前测试用户。返回 (coupon_id, user_coupon_id)。"""
    payload = {
        "name": name,
        "type": type,
        "condition_amount": condition_amount,
        "discount_value": discount_value,
        "discount_rate": discount_rate,
        "scope": scope,
        "scope_ids": scope_ids,
        "validity_days": validity_days,
        "status": "active",
        "total_count": 100,
    }
    resp = await client.post("/api/admin/coupons", json=payload, headers=admin_headers)
    assert resp.status_code in (200, 201), resp.text
    coupon = resp.json()
    coupon_id = coupon["id"]

    user_coupon_id = None
    if grant_to_self:
        claim = await client.post(
            "/api/coupons/claim",
            json={"coupon_id": coupon_id},
            headers=auth_headers,
        )
        if claim.status_code == 200:
            mine = await client.get("/api/coupons/mine?tab=unused", headers=auth_headers)
            assert mine.status_code == 200
            items = mine.json().get("items") or []
            for it in items:
                if it["coupon_id"] == coupon_id:
                    user_coupon_id = it["id"]
                    break
    return coupon_id, user_coupon_id


@pytest.mark.asyncio
async def test_b1_free_trial_coupon_zero_payment(
    client: AsyncClient, admin_headers, auth_headers
):
    """B1: 免费试用券下单时，应付金额必须为 0（即便 product 售价 99）。"""
    pid = await _create_product(
        client, admin_headers,
        name="免费试用商品", cat_name="UsableCoupon-FT-Cat", sale_price=99.0,
    )
    cid, ucid = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="免费试用券A", type="free_trial",
        condition_amount=0, discount_value=0,
        scope="product", scope_ids=[pid],
    )
    assert cid > 0

    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "payment_method": "wechat",
            "coupon_id": cid,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    order = resp.json()
    # 总额=99，免费试用应抵扣到 0
    assert float(order["total_amount"]) == 99.0
    assert float(order["paid_amount"]) == 0.0, (
        f"免费试用券下单的 paid_amount 必须为 0；实际={order['paid_amount']}"
    )


@pytest.mark.asyncio
async def test_b3_usable_endpoint_filters_scope_product(
    client: AsyncClient, admin_headers, auth_headers
):
    """B3: scope=product 的券若不命中本商品 → 不出现在列表中；命中 → 出现。"""
    pid_a = await _create_product(client, admin_headers, name="商品A", cat_name="Usable-A")
    pid_b = await _create_product(client, admin_headers, name="商品B", cat_name="Usable-B")

    # 仅适用于商品 A 的券
    cid_a, _ = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="A专享券", type="voucher",
        condition_amount=0, discount_value=10,
        scope="product", scope_ids=[pid_a],
    )

    # 用商品 B 的下单上下文请求接口 → A 券不应出现
    resp_b = await client.get(
        "/api/coupons/usable-for-order",
        params={"product_id": pid_b, "subtotal": 100},
        headers=auth_headers,
    )
    assert resp_b.status_code == 200, resp_b.text
    items_b = resp_b.json().get("items") or []
    assert all(it["coupon_id"] != cid_a for it in items_b), (
        f"A专享券不应出现在商品B的下单页券列表中；实际={items_b}"
    )

    # 用商品 A 的下单上下文 → A 券应出现
    resp_a = await client.get(
        "/api/coupons/usable-for-order",
        params={"product_id": pid_a, "subtotal": 100},
        headers=auth_headers,
    )
    assert resp_a.status_code == 200, resp_a.text
    items_a = resp_a.json().get("items") or []
    assert any(it["coupon_id"] == cid_a for it in items_a), (
        f"A专享券应出现在商品A的下单页券列表中；实际={items_a}"
    )


@pytest.mark.asyncio
async def test_b3_usable_endpoint_filters_offline_coupon(
    client: AsyncClient, admin_headers, auth_headers, db_session
):
    """B3: 已下架的券不应出现在下单页列表中。"""
    from app.models.models import Coupon

    pid = await _create_product(client, admin_headers, name="商品X", cat_name="Usable-Offline")

    cid, _ = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="待下架券", type="voucher",
        condition_amount=0, discount_value=5,
        scope="all",
    )

    # 直接改 DB 字段模拟下架（避开 is_superuser 校验）
    rs = await db_session.execute(select(Coupon).where(Coupon.id == cid))
    c = rs.scalar_one()
    c.is_offline = True
    await db_session.commit()

    resp = await client.get(
        "/api/coupons/usable-for-order",
        params={"product_id": pid, "subtotal": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    assert all(it["coupon_id"] != cid for it in items), (
        f"已下架券不应出现在下单页券列表中；实际={items}"
    )


@pytest.mark.asyncio
async def test_b3_usable_endpoint_respects_condition_amount(
    client: AsyncClient, admin_headers, auth_headers
):
    """B3: subtotal < condition_amount 的非 free_trial 券不应出现；free_trial 强制忽略门槛。"""
    pid = await _create_product(client, admin_headers, name="商品Y", cat_name="Usable-Cond")

    # 满 200 减 30 的券
    cid_full, _ = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="满200减30", type="full_reduction",
        condition_amount=200, discount_value=30, scope="all",
    )
    # 免费试用券（condition_amount=0 即可，但接口逻辑必须忽略 subtotal 比对）
    cid_ft, _ = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="试用FT", type="free_trial",
        condition_amount=0, discount_value=0,
        scope="product", scope_ids=[pid],
    )

    # subtotal=100：满200减30 不应出现；试用券应出现
    resp = await client.get(
        "/api/coupons/usable-for-order",
        params={"product_id": pid, "subtotal": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    coupon_ids = [it["coupon_id"] for it in items]
    assert cid_full not in coupon_ids, "subtotal=100 时满200减30不应出现"
    assert cid_ft in coupon_ids, "免费试用券必须忽略 condition_amount，始终出现"

    # subtotal=300：两张券都应出现
    resp2 = await client.get(
        "/api/coupons/usable-for-order",
        params={"product_id": pid, "subtotal": 300},
        headers=auth_headers,
    )
    items2 = resp2.json().get("items") or []
    coupon_ids2 = [it["coupon_id"] for it in items2]
    assert cid_full in coupon_ids2, "subtotal=300 时满200减30应出现"
    assert cid_ft in coupon_ids2, "免费试用券任何 subtotal 下都应出现"


@pytest.mark.asyncio
async def test_b3_usable_endpoint_filters_expired_coupon(
    client: AsyncClient, admin_headers, auth_headers, db_session
):
    """B3: 已过期（expire_at <= now）的券不应出现在下单页列表中。"""
    from app.models.models import UserCoupon

    pid = await _create_product(client, admin_headers, name="商品Z", cat_name="Usable-Expired")

    cid, ucid = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="即将过期券", type="voucher",
        condition_amount=0, discount_value=5, scope="all",
        validity_days=30,
    )
    assert ucid is not None

    # 直接修改 user_coupon.expire_at 到过去
    rs = await db_session.execute(select(UserCoupon).where(UserCoupon.id == ucid))
    uc = rs.scalar_one()
    uc.expire_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    resp = await client.get(
        "/api/coupons/usable-for-order",
        params={"product_id": pid, "subtotal": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    assert all(it["coupon_id"] != cid for it in items), (
        f"已过期券不应出现在下单页券列表中；实际={items}"
    )


@pytest.mark.asyncio
async def test_create_order_rejects_inapplicable_coupon(
    client: AsyncClient, admin_headers, auth_headers
):
    """创单兜底（B3 后端）：用户篡改 coupon_id 用「适用其他商品」的券下单，应返回 422。"""
    pid_a = await _create_product(client, admin_headers, name="商品AA", cat_name="Reject-A")
    pid_b = await _create_product(client, admin_headers, name="商品BB", cat_name="Reject-B")

    cid_a, _ = await _create_and_grant_coupon(
        client, admin_headers, auth_headers,
        name="A专享券-Reject", type="voucher",
        condition_amount=0, discount_value=10,
        scope="product", scope_ids=[pid_a],
    )

    # 用商品 B 下单却带 A 专享券
    resp = await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": pid_b, "quantity": 1}],
            "payment_method": "wechat",
            "coupon_id": cid_a,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422, (
        f"用不适用的券下单应返回 422；实际 status={resp.status_code} body={resp.text}"
    )
    assert "不适用" in resp.text or "不可用" in resp.text
