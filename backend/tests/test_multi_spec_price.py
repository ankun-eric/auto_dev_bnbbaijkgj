"""Tests for Bug Fix: 多规格商品价格显示0

验证 ProductResponse._compute_min_price model_validator 在各场景下的正确性：
- 多规格商品从 SKU 表计算最低价
- 单规格商品保持主表 sale_price
- 所有 SKU 价格相同时 has_multi_spec=False
- 所有 SKU 停用时回退到主表 sale_price
- 通过 API 列表接口验证多规格商品包含正确的 min_price / has_multi_spec
"""

from datetime import datetime

import pytest
from httpx import AsyncClient

from app.models.models import Product, ProductCategory, ProductSku
from app.schemas.products import ProductResponse, ProductSkuResponse
from tests.conftest import test_session


def _make_sku_response(sale_price: float, status: int = 1, **kwargs) -> ProductSkuResponse:
    defaults = {
        "id": 1,
        "product_id": 1,
        "spec_name": "default",
        "sale_price": sale_price,
        "origin_price": None,
        "stock": 10,
        "is_default": False,
        "status": status,
        "sort_order": 0,
        "has_orders": False,
    }
    defaults.update(kwargs)
    return ProductSkuResponse(**defaults)


def _make_product_response(
    sale_price: float,
    spec_mode: int = 1,
    skus: list[ProductSkuResponse] | None = None,
) -> ProductResponse:
    now = datetime.utcnow()
    return ProductResponse(
        id=1,
        name="测试商品",
        category_id=1,
        fulfillment_type="in_store",
        original_price=None,
        sale_price=sale_price,
        images=[],
        stock=100,
        points_exchangeable=False,
        points_price=0,
        points_deductible=False,
        redeem_count=1,
        appointment_mode="none",
        recommend_weight=0,
        sales_count=0,
        status="active",
        sort_order=0,
        spec_mode=spec_mode,
        skus=skus or [],
        created_at=now,
        updated_at=now,
    )


# ──────────────── 1. 多规格商品最低价计算 ────────────────

@pytest.mark.asyncio
async def test_multi_spec_product_min_price():
    """多规格商品（spec_mode=2），3个SKU售价分别1300/1800/2500，
    验证 min_price=1300, sale_price=1300, has_multi_spec=True"""
    skus = [
        _make_sku_response(1300, status=1, id=1, spec_name="基础款"),
        _make_sku_response(1800, status=1, id=2, spec_name="标准款"),
        _make_sku_response(2500, status=1, id=3, spec_name="豪华款"),
    ]
    resp = _make_product_response(sale_price=0, spec_mode=2, skus=skus)

    assert resp.min_price == 1300
    assert resp.sale_price == 1300
    assert resp.has_multi_spec is True


# ──────────────── 2. 单规格商品价格 ────────────────

@pytest.mark.asyncio
async def test_single_spec_product_price():
    """单规格商品（spec_mode=1），sale_price=500，
    验证 min_price=500, has_multi_spec=False"""
    resp = _make_product_response(sale_price=500, spec_mode=1)

    assert resp.min_price == 500
    assert resp.sale_price == 500
    assert resp.has_multi_spec is False


# ──────────────── 3. 多规格商品所有SKU价格相同 ────────────────

@pytest.mark.asyncio
async def test_multi_spec_same_price():
    """多规格商品所有SKU价格相同（都是1000），
    验证 has_multi_spec=False（价格无差异则不标记为多规格差价）"""
    skus = [
        _make_sku_response(1000, status=1, id=1, spec_name="规格A"),
        _make_sku_response(1000, status=1, id=2, spec_name="规格B"),
    ]
    resp = _make_product_response(sale_price=0, spec_mode=2, skus=skus)

    assert resp.min_price == 1000
    assert resp.sale_price == 1000
    assert resp.has_multi_spec is False


# ──────────────── 4. 多规格商品所有SKU停用 ────────────────

@pytest.mark.asyncio
async def test_multi_spec_no_enabled_skus():
    """多规格商品所有SKU都非启用状态（status=2），
    验证回退到主表 sale_price"""
    skus = [
        _make_sku_response(1200, status=2, id=1, spec_name="停用A"),
        _make_sku_response(1500, status=2, id=2, spec_name="停用B"),
    ]
    resp = _make_product_response(sale_price=888, spec_mode=2, skus=skus)

    assert resp.min_price == 888
    assert resp.sale_price == 888


# ──────────────── 5. API列表接口返回正确的min_price ────────────────

async def _ensure_category(client: AsyncClient, admin_headers, name="价格测试分类") -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_multi_spec_product_in_list_api(client: AsyncClient, admin_headers):
    """通过API请求商品列表，验证返回的多规格商品包含正确的 min_price 和 has_multi_spec"""
    cid = await _ensure_category(client, admin_headers, "列表API测试")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "列表多规格验证",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "sale_price": 0,
            "stock": 100,
            "status": "active",
            "spec_mode": 2,
            "images": ["https://img.example.com/test.jpg"],
            "skus": [
                {"spec_name": "小份", "sale_price": 800, "stock": 20, "is_default": True, "status": 1},
                {"spec_name": "大份", "sale_price": 1500, "stock": 10, "status": 1},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    product_id = resp.json()["id"]

    list_resp = await client.get(f"/api/products?category_id={cid}")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]

    target = next((p for p in items if p["id"] == product_id), None)
    assert target is not None, f"商品 {product_id} 未出现在列表中"
    assert target["min_price"] == 800
    assert target["sale_price"] == 800
    assert target["has_multi_spec"] is True
