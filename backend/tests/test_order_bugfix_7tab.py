"""Tests for order system bugfix: 7-tab unified orders + refund_status filter.

Covers:
1. GET /api/orders/unified/counts returns all 8 keys (all / pending_payment /
   pending_receipt / pending_use / completed / pending_review / cancelled / refund)
2. GET /api/orders/unified supports refund_status param (all_refund / multi / single)
3. GET /api/orders/unified supports 7-tab status values
4. Old endpoints /api/orders and /api/admin/orders (non-/unified) return 404
"""

import pytest
from httpx import AsyncClient

from app.models.models import Product, ProductCategory
from tests.conftest import test_session


# ────────────────────── helpers ──────────────────────


async def _seed_category(name="订单测试分类") -> int:
    async with test_session() as db:
        cat = ProductCategory(name=name, status="active", sort_order=0, level=1)
        db.add(cat)
        await db.commit()
        return cat.id


async def _seed_product(category_id: int, *, name="订单测试商品", stock=100) -> int:
    async with test_session() as db:
        product = Product(
            name=name,
            category_id=category_id,
            fulfillment_type="delivery",
            original_price=199.0,
            sale_price=99.0,
            images=["https://img.example.com/1.jpg"],
            stock=stock,
            status="active",
            points_exchangeable=False,
            redeem_count=1,
            appointment_mode="none",
        )
        db.add(product)
        await db.commit()
        return product.id


async def _create_order(client: AsyncClient, auth_headers: dict, product_id: int, quantity=1):
    return await client.post(
        "/api/orders/unified",
        json={
            "items": [{"product_id": product_id, "quantity": quantity}],
            "payment_method": "wechat",
            "points_deduction": 0,
        },
        headers=auth_headers,
    )


# ═══════════════════════════════════════════════════════
#  1. /api/orders/unified/counts — 8 个 key 完整性
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_counts_all_keys(client: AsyncClient, auth_headers):
    """计数接口必须返回全部 8 个 tab 字段，值均为非负整数。"""
    resp = await client.get("/api/orders/unified/counts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    expected_keys = {
        "all",
        "pending_payment",
        "pending_receipt",
        "pending_use",
        "completed",
        "pending_review",
        "cancelled",
        "refund",
    }
    assert set(data.keys()) >= expected_keys, f"缺失字段: {expected_keys - set(data.keys())}"

    for k in expected_keys:
        v = data[k]
        assert isinstance(v, int), f"{k} 应该是 int，实际是 {type(v).__name__}"
        assert v >= 0, f"{k} 应该 >= 0，实际 {v}"


@pytest.mark.asyncio
async def test_counts_with_data(client: AsyncClient, auth_headers):
    """创建订单后 all 与 pending_payment 计数应 >= 1。"""
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id)
    await _create_order(client, auth_headers, pid)

    resp = await client.get("/api/orders/unified/counts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["all"] >= 1
    assert data["pending_payment"] >= 1


# ═══════════════════════════════════════════════════════
#  2. /api/orders/unified 列表接口 — 基础 & refund_status
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_without_status(client: AsyncClient, auth_headers):
    """不传 status 时应返回 200 + {items, total}。"""
    resp = await client.get("/api/orders/unified", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and isinstance(data["items"], list)
    assert "total" in data and isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_list_with_refund_status_all_refund(client: AsyncClient, auth_headers):
    """refund_status=all_refund 应返回 200（聚合所有退款状态）。"""
    resp = await client.get(
        "/api/orders/unified",
        params={"refund_status": "all_refund"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_with_refund_status_multi(client: AsyncClient, auth_headers):
    """refund_status=applied,reviewing 多值（逗号分隔）应返回 200。"""
    resp = await client.get(
        "/api/orders/unified",
        params={"refund_status": "applied,reviewing"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_with_refund_status_single(client: AsyncClient, auth_headers):
    """refund_status=applied 单值应返回 200。"""
    resp = await client.get(
        "/api/orders/unified",
        params={"refund_status": "applied"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


# ═══════════════════════════════════════════════════════
#  3. 7 个 tab status 值全部可过滤
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_val",
    [
        "pending_payment",
        "pending_receipt",
        "pending_use",
        "completed",
        "pending_review",
        "cancelled",
    ],
)
async def test_list_with_7_tab_statuses(client: AsyncClient, auth_headers, status_val):
    """每个 tab 的 status 过滤都应返回 200 且结构合法。"""
    resp = await client.get(
        "/api/orders/unified",
        params={"status": status_val},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"status={status_val} 返回 {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_list_with_status_all(client: AsyncClient, auth_headers):
    """status=all（第 1 个 tab）不做状态过滤，应返回 200。"""
    resp = await client.get(
        "/api/orders/unified",
        params={"status": "all"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════
#  4. 老接口已下线（404）
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_old_orders_api_disabled(client: AsyncClient, auth_headers):
    """GET /api/orders 老接口已下线，应返回 404。"""
    resp = await client.get("/api/orders", headers=auth_headers)
    assert resp.status_code == 404, (
        f"老接口 /api/orders 应返回 404，实际 {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_old_orders_api_disabled_no_auth(client: AsyncClient):
    """无鉴权访问 /api/orders 也应 404（路由不存在优先于 401）。"""
    resp = await client.get("/api/orders")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_old_admin_orders_api_disabled(client: AsyncClient, admin_headers):
    """GET /api/admin/orders（非 unified）已下线，admin 认证后仍应 404。"""
    resp = await client.get("/api/admin/orders", headers=admin_headers)
    assert resp.status_code in (404, 405), (
        f"老接口 /api/admin/orders 应返回 404/405，实际 {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_old_admin_orders_api_disabled_no_auth(client: AsyncClient):
    """未鉴权访问 /api/admin/orders 允许 404/401/405（路由已卸载即视为下线）。"""
    resp = await client.get("/api/admin/orders")
    assert resp.status_code in (401, 403, 404, 405)


# ═══════════════════════════════════════════════════════
#  5. 新接口仍可用（回归验证）
# ═══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_unified_admin_orders_still_available(client: AsyncClient, admin_headers):
    """/api/admin/orders/unified 新接口仍应可用（200）。"""
    resp = await client.get("/api/admin/orders/unified", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
