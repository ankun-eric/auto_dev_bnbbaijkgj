"""Tests for the unified product system (商品体系整合).

Covers: product categories, products, unified orders, favorites,
coupons, addresses, member QR code, and admin product management APIs.
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.models import (
    Coupon,
    CouponStatus,
    Product,
    ProductCategory,
    UnifiedOrder,
    UnifiedOrderStatus,
    UserAddress,
)
from tests.conftest import test_session


# ────────────────────── helpers ──────────────────────


async def _seed_category(name="测试分类", status="active", parent_id=None, level=1) -> int:
    async with test_session() as db:
        cat = ProductCategory(
            name=name, status=status, sort_order=0, level=level, parent_id=parent_id,
        )
        db.add(cat)
        await db.commit()
        return cat.id


async def _seed_product(
    category_id: int,
    *,
    name="测试商品",
    stock=100,
    sale_price=99.0,
    original_price=199.0,
    fulfillment_type="delivery",
    status="active",
    points_exchangeable=False,
) -> int:
    async with test_session() as db:
        product = Product(
            name=name,
            category_id=category_id,
            fulfillment_type=fulfillment_type,
            original_price=original_price,
            sale_price=sale_price,
            images=["https://img.example.com/1.jpg"],
            stock=stock,
            status=status,
            points_exchangeable=points_exchangeable,
            redeem_count=1,
            appointment_mode="none",
        )
        db.add(product)
        await db.commit()
        return product.id


async def _seed_coupon(
    name="满100减10",
    coupon_type="full_reduction",
    condition_amount=100,
    discount_value=10,
    total_count=100,
    valid_days=30,
    status="active",
) -> int:
    async with test_session() as db:
        coupon = Coupon(
            name=name,
            type=coupon_type,
            condition_amount=condition_amount,
            discount_value=discount_value,
            total_count=total_count,
            valid_start=datetime.utcnow() - timedelta(days=1),
            valid_end=datetime.utcnow() + timedelta(days=valid_days),
            status=status,
        )
        db.add(coupon)
        await db.commit()
        return coupon.id


async def _create_order(client: AsyncClient, auth_headers: dict, product_id: int, quantity=1):
    resp = await client.post("/api/orders/unified", json={
        "items": [{"product_id": product_id, "quantity": quantity}],
        "payment_method": "wechat",
        "points_deduction": 0,
    }, headers=auth_headers)
    return resp


# ═══════════════════════════════════════════════════════
#  1. 商品分类 API
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_001_list_categories(client: AsyncClient):
    """TC-001: 获取分类列表 — 正常返回"""
    await _seed_category("健康服务")
    await _seed_category("体检套餐")

    resp = await client.get("/api/products/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_tc_002_list_categories_empty(client: AsyncClient):
    """TC-002: 获取分类列表 — 空列表"""
    resp = await client.get("/api/products/categories")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ═══════════════════════════════════════════════════════
#  2. 商品列表 API
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_003_list_products_pagination(client: AsyncClient):
    """TC-003: 获取商品列表 — 正常分页"""
    cat_id = await _seed_category()
    for i in range(3):
        await _seed_product(cat_id, name=f"商品{i}")

    resp = await client.get("/api/products", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_tc_004_list_products_by_category(client: AsyncClient):
    """TC-004: 获取商品列表 — 按分类筛选"""
    cat_a = await _seed_category("分类A")
    cat_b = await _seed_category("分类B")
    await _seed_product(cat_a, name="A商品")
    await _seed_product(cat_b, name="B商品")

    resp = await client.get("/api/products", params={"category_id": cat_a})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "A商品"


@pytest.mark.asyncio
async def test_tc_005_list_products_keyword_search(client: AsyncClient):
    """TC-005: 获取商品列表 — 按关键字搜索"""
    cat_id = await _seed_category()
    await _seed_product(cat_id, name="维生素C片")
    await _seed_product(cat_id, name="钙片")

    resp = await client.get("/api/products", params={"keyword": "维生素"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert "维生素" in data["items"][0]["name"]


@pytest.mark.asyncio
async def test_tc_006_list_products_points_exchangeable(client: AsyncClient):
    """TC-006: 获取商品列表 — 积分可兑换筛选"""
    cat_id = await _seed_category()
    await _seed_product(cat_id, name="普通商品", points_exchangeable=False)
    await _seed_product(cat_id, name="积分商品", points_exchangeable=True)

    resp = await client.get("/api/products", params={"points_exchangeable": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "积分商品"


# ═══════════════════════════════════════════════════════
#  3. 商品详情 API
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_007_get_product_detail(client: AsyncClient):
    """TC-007: 获取商品详情 — 正常"""
    cat_id = await _seed_category("健康体检")
    pid = await _seed_product(cat_id, name="全身体检套餐", sale_price=299.0)

    resp = await client.get(f"/api/products/{pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pid
    assert data["name"] == "全身体检套餐"
    assert data["sale_price"] == 299.0
    assert data["category_name"] == "健康体检"


@pytest.mark.asyncio
async def test_tc_008_get_product_not_found(client: AsyncClient):
    """TC-008: 获取商品详情 — 不存在的商品 (404)"""
    resp = await client.get("/api/products/99999")
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════
#  4. 创建统一订单
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_009_create_unified_order(client: AsyncClient, auth_headers):
    """TC-009: 创建订单 — 正常"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, sale_price=100.0, stock=50)

    resp = await _create_order(client, auth_headers, pid, quantity=2)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_amount"] == 200.0
    assert data["order_no"].startswith("UO")
    assert data["status"] == "pending_payment"
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == pid
    assert data["items"][0]["quantity"] == 2


@pytest.mark.asyncio
async def test_tc_010_create_order_unauthorized(client: AsyncClient):
    """TC-010: 创建订单 — 未登录 (401)"""
    resp = await client.post("/api/orders/unified", json={
        "items": [{"product_id": 1, "quantity": 1}],
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tc_011_create_order_insufficient_stock(client: AsyncClient, auth_headers):
    """TC-011: 创建订单 — 库存不足"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, stock=1)

    resp = await _create_order(client, auth_headers, pid, quantity=10)
    assert resp.status_code == 400
    assert "库存不足" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════
#  5. 订单管理
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_012_list_unified_orders(client: AsyncClient, auth_headers):
    """TC-012: 获取订单列表"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, stock=100)
    await _create_order(client, auth_headers, pid)
    await _create_order(client, auth_headers, pid)

    resp = await client.get("/api/orders/unified", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_tc_013_get_unified_order_detail(client: AsyncClient, auth_headers):
    """TC-013: 获取订单详情"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    resp = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == order_id


@pytest.mark.asyncio
async def test_tc_014_pay_unified_order(client: AsyncClient, auth_headers):
    """TC-014: 支付订单"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    resp = await client.post(f"/api/orders/unified/{order_id}/pay", json={
        "payment_method": "wechat",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert "支付成功" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc_015_cancel_unified_order(client: AsyncClient, auth_headers):
    """TC-015: 取消订单"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    resp = await client.post(f"/api/orders/unified/{order_id}/cancel", json={
        "cancel_reason": "不想要了",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert "取消" in resp.json()["message"]

    detail = await client.get(f"/api/orders/unified/{order_id}", headers=auth_headers)
    assert detail.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_tc_016_confirm_receipt(client: AsyncClient, auth_headers):
    """TC-016: 确认收货"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, fulfillment_type="delivery")

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    await client.post(f"/api/orders/unified/{order_id}/pay", json={
        "payment_method": "wechat",
    }, headers=auth_headers)

    async with test_session() as db:
        from sqlalchemy import select
        result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
        order = result.scalar_one()
        order.status = UnifiedOrderStatus.pending_receipt
        await db.commit()

    resp = await client.post(f"/api/orders/unified/{order_id}/confirm", headers=auth_headers)
    assert resp.status_code == 200
    assert "收货" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc_017_review_order(client: AsyncClient, auth_headers):
    """TC-017: 提交评价"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    await client.post(f"/api/orders/unified/{order_id}/pay", json={
        "payment_method": "wechat",
    }, headers=auth_headers)

    async with test_session() as db:
        from sqlalchemy import select
        result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
        order = result.scalar_one()
        order.status = UnifiedOrderStatus.pending_review
        await db.commit()

    resp = await client.post(f"/api/orders/unified/{order_id}/review", json={
        "rating": 5,
        "content": "非常满意",
        "images": ["https://img.example.com/review1.jpg"],
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert "评价成功" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc_018_request_refund(client: AsyncClient, auth_headers):
    """TC-018: 申请退款"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    await client.post(f"/api/orders/unified/{order_id}/pay", json={
        "payment_method": "wechat",
    }, headers=auth_headers)

    resp = await client.post(f"/api/orders/unified/{order_id}/refund", json={
        "reason": "商品与描述不符",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "退款" in data["message"]
    assert "refund_id" in data


# ═══════════════════════════════════════════════════════
#  6. 收藏功能
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_019_add_favorite(client: AsyncClient, auth_headers):
    """TC-019: 收藏商品"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    resp = await client.post(
        "/api/favorites",
        params={"content_type": "product", "content_id": pid},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_favorited"] is True


@pytest.mark.asyncio
async def test_tc_020_remove_favorite(client: AsyncClient, auth_headers):
    """TC-020: 取消收藏"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    await client.post(
        "/api/favorites",
        params={"content_type": "product", "content_id": pid},
        headers=auth_headers,
    )

    resp = await client.post(
        "/api/favorites",
        params={"content_type": "product", "content_id": pid},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_favorited"] is False


@pytest.mark.asyncio
async def test_tc_021_list_favorites(client: AsyncClient, auth_headers):
    """TC-021: 获取收藏列表"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    await client.post(
        "/api/favorites",
        params={"content_type": "product", "content_id": pid},
        headers=auth_headers,
    )

    resp = await client.get("/api/favorites", params={"tab": "product"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["content_type"] == "product"


# ═══════════════════════════════════════════════════════
#  7. 优惠券
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_022_list_available_coupons(client: AsyncClient, auth_headers):
    """TC-022: 获取可领取优惠券"""
    await _seed_coupon("满50减5", total_count=50)

    resp = await client.get("/api/coupons/available", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_tc_023_claim_coupon(client: AsyncClient, auth_headers):
    """TC-023: 领取优惠券"""
    coupon_id = await _seed_coupon("满100减10")

    resp = await client.post("/api/coupons/claim", json={
        "coupon_id": coupon_id,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert "领取成功" in resp.json()["message"]

    dup = await client.post("/api/coupons/claim", json={
        "coupon_id": coupon_id,
    }, headers=auth_headers)
    assert dup.status_code == 400


@pytest.mark.asyncio
async def test_tc_024_list_my_coupons(client: AsyncClient, auth_headers):
    """TC-024: 我的优惠券列表"""
    coupon_id = await _seed_coupon()
    await client.post("/api/coupons/claim", json={"coupon_id": coupon_id}, headers=auth_headers)

    resp = await client.get("/api/coupons/mine", params={"tab": "unused"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


# ═══════════════════════════════════════════════════════
#  8. 地址管理
# ═══════════════════════════════════════════════════════


_ADDR_PAYLOAD = {
    "name": "张三",
    "phone": "13800001111",
    "province": "北京市",
    "city": "北京市",
    "district": "朝阳区",
    "street": "望京SOHO T1 1001",
    "is_default": True,
}


@pytest.mark.asyncio
async def test_tc_025_create_address(client: AsyncClient, auth_headers):
    """TC-025: 新增地址"""
    resp = await client.post("/api/addresses", json=_ADDR_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "张三"
    assert data["is_default"] is True


@pytest.mark.asyncio
async def test_tc_026_list_addresses(client: AsyncClient, auth_headers):
    """TC-026: 获取地址列表"""
    await client.post("/api/addresses", json=_ADDR_PAYLOAD, headers=auth_headers)

    resp = await client.get("/api/addresses", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_tc_027_update_address(client: AsyncClient, auth_headers):
    """TC-027: 修改地址"""
    create_resp = await client.post("/api/addresses", json=_ADDR_PAYLOAD, headers=auth_headers)
    addr_id = create_resp.json()["id"]

    resp = await client.put(f"/api/addresses/{addr_id}", json={
        "street": "望京SOHO T2 2002",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["street"] == "望京SOHO T2 2002"


@pytest.mark.asyncio
async def test_tc_028_delete_address(client: AsyncClient, auth_headers):
    """TC-028: 删除地址"""
    create_resp = await client.post("/api/addresses", json=_ADDR_PAYLOAD, headers=auth_headers)
    addr_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/addresses/{addr_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert "删除" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc_029_address_limit(client: AsyncClient, auth_headers):
    """TC-029: 超过10个地址限制"""
    for i in range(10):
        payload = {**_ADDR_PAYLOAD, "name": f"用户{i}", "is_default": False}
        r = await client.post("/api/addresses", json=payload, headers=auth_headers)
        assert r.status_code == 200

    resp = await client.post("/api/addresses", json={
        **_ADDR_PAYLOAD, "name": "第11个", "is_default": False,
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "10" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════
#  9. 会员码
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_030_get_member_qrcode(client: AsyncClient, auth_headers):
    """TC-030: 获取会员码"""
    resp = await client.get("/api/member/qrcode", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "expires_at" in data
    assert len(data["token"]) == 32


# ═══════════════════════════════════════════════════════
#  10. 管理后台 API
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc_031_admin_create_category(client: AsyncClient, admin_headers):
    """TC-031: 创建商品分类"""
    resp = await client.post("/api/admin/products/categories", json={
        "name": "口腔护理",
        "sort_order": 1,
        "status": "active",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "口腔护理"
    assert data["level"] == 1


@pytest.mark.asyncio
async def test_tc_032_admin_create_product(client: AsyncClient, admin_headers):
    """TC-032: 创建商品"""
    cat_resp = await client.post("/api/admin/products/categories", json={
        "name": "中医推拿",
        "status": "active",
    }, headers=admin_headers)
    cat_id = cat_resp.json()["id"]

    resp = await client.post("/api/admin/products", json={
        "name": "全身推拿60分钟",
        "category_id": cat_id,
        "fulfillment_type": "in_store",
        "original_price": 399.0,
        "sale_price": 299.0,
        "stock": 200,
        "status": "active",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "全身推拿60分钟"
    assert data["sale_price"] == 299.0


@pytest.mark.asyncio
async def test_tc_033_admin_update_product(client: AsyncClient, admin_headers):
    """TC-033: 编辑商品"""
    cat_resp = await client.post("/api/admin/products/categories", json={
        "name": "理疗", "status": "active",
    }, headers=admin_headers)
    cat_id = cat_resp.json()["id"]

    create_resp = await client.post("/api/admin/products", json={
        "name": "肩颈理疗",
        "category_id": cat_id,
        "fulfillment_type": "in_store",
        "original_price": 200.0,
        "sale_price": 150.0,
        "stock": 50,
        "status": "active",
    }, headers=admin_headers)
    pid = create_resp.json()["id"]

    resp = await client.put(f"/api/admin/products/{pid}", json={
        "sale_price": 129.0,
        "stock": 80,
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["sale_price"] == 129.0
    assert resp.json()["stock"] == 80


@pytest.mark.asyncio
async def test_tc_034_admin_list_orders(client: AsyncClient, admin_headers, auth_headers):
    """TC-034: 管理订单列表"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)
    await _create_order(client, auth_headers, pid)

    resp = await client.get("/api/admin/orders/unified", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_tc_035_admin_ship_order(client: AsyncClient, admin_headers, auth_headers):
    """TC-035: 发货操作"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, fulfillment_type="delivery")

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    await client.post(f"/api/orders/unified/{order_id}/pay", json={
        "payment_method": "wechat",
    }, headers=auth_headers)

    resp = await client.post(f"/api/admin/orders/unified/{order_id}/ship", json={
        "tracking_company": "顺丰速运",
        "tracking_number": "SF1234567890",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert "发货成功" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc_036_admin_refund_review(client: AsyncClient, admin_headers, auth_headers):
    """TC-036: 退款审核"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)

    create_resp = await _create_order(client, auth_headers, pid)
    order_id = create_resp.json()["id"]

    await client.post(f"/api/orders/unified/{order_id}/pay", json={
        "payment_method": "wechat",
    }, headers=auth_headers)

    await client.post(f"/api/orders/unified/{order_id}/refund", json={
        "reason": "质量问题",
    }, headers=auth_headers)

    resp = await client.post(
        f"/api/admin/orders/unified/{order_id}/refund/approve",
        json={"admin_notes": "已核实，同意退款"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "批准" in resp.json()["message"]
