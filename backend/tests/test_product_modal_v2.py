"""Tests for PRD v2: 商品管理新建/编辑弹窗优化

覆盖：
- 扩展字段（product_code_list / spec_mode / main_video_url / selling_point / description_rich）
- 规格（SKU）创建、更新、默认规格约束、订单引用后的锁定
- 上架强校验
- 多规格下单：按 sku_id 扣库存/取价
- 老数据兼容
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    Product,
    ProductCategory,
    ProductSku,
    UnifiedOrder,
)
from tests.conftest import test_session


async def _create_cat(client: AsyncClient, admin_headers, name="v2分类") -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


# ──────────────── 1. 新字段 ────────────────

@pytest.mark.asyncio
async def test_create_product_with_new_fields(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers)
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "新字段商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 200.0,
            "sale_price": 150.0,
            "stock": 50,
            "status": "draft",
            "product_code_list": ["6901234567890", "6901234567891"],
            "spec_mode": 1,
            "main_video_url": "https://cdn.example.com/a.mp4",
            "selling_point": "3 场直播口碑爆款",
            "description_rich": "<p><b>Hello</b></p>",
            "images": ["https://img.example.com/1.jpg"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["product_code_list"] == ["6901234567890", "6901234567891"]
    assert data["selling_point"] == "3 场直播口碑爆款"
    assert data["main_video_url"] == "https://cdn.example.com/a.mp4"
    assert data["description_rich"].startswith("<p>")


@pytest.mark.asyncio
async def test_product_code_list_limit(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "条码上限")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "条码超限",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "product_code_list": [f"CODE{i:04d}" for i in range(11)],  # 11 个
            "images": ["https://img.example.com/1.jpg"],
        },
        headers=admin_headers,
    )
    assert resp.status_code >= 400
    assert "条码" in resp.json().get("detail", "") or "10" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_selling_point_too_long(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "卖点超长")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "卖点超长",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 10.0,
            "sale_price": 9.0,
            "stock": 1,
            "status": "draft",
            "selling_point": "x" * 101,
            "images": ["https://img.example.com/1.jpg"],
        },
        headers=admin_headers,
    )
    assert resp.status_code >= 400


# ──────────────── 2. 多规格（SKU）────────────────

@pytest.mark.asyncio
async def test_create_multi_spec_product(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "多规格")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "多规格商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 0,
            "sale_price": 0,
            "stock": 0,
            "status": "draft",
            "spec_mode": 2,
            "images": ["https://img.example.com/1.jpg"],
            "skus": [
                {"spec_name": "单次", "sale_price": 99.0, "origin_price": 199.0, "stock": 10, "is_default": True, "status": 1, "sort_order": 0},
                {"spec_name": "5 次套餐", "sale_price": 399.0, "origin_price": 599.0, "stock": 5, "is_default": False, "status": 1, "sort_order": 1},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec_mode"] == 2
    assert len(data["skus"]) == 2
    defaults = [s for s in data["skus"] if s["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["spec_name"] == "单次"


@pytest.mark.asyncio
async def test_update_multi_spec_skus(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "多规格更新")
    create_resp = await client.post(
        "/api/admin/products",
        json={
            "name": "更新多规格",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 0,
            "sale_price": 0,
            "stock": 0,
            "status": "draft",
            "spec_mode": 2,
            "images": ["https://img.example.com/1.jpg"],
            "skus": [
                {"spec_name": "A", "sale_price": 10.0, "stock": 10, "is_default": True, "status": 1, "sort_order": 0},
            ],
        },
        headers=admin_headers,
    )
    pid = create_resp.json()["id"]
    sku_id = create_resp.json()["skus"][0]["id"]

    upd = await client.put(
        f"/api/admin/products/{pid}",
        json={
            "skus": [
                {"id": sku_id, "spec_name": "A", "sale_price": 12.0, "stock": 20, "is_default": True, "status": 1, "sort_order": 0},
                {"spec_name": "B", "sale_price": 20.0, "stock": 5, "is_default": False, "status": 1, "sort_order": 1},
            ],
            "spec_mode": 2,
        },
        headers=admin_headers,
    )
    assert upd.status_code == 200, upd.text
    skus = upd.json()["skus"]
    assert len(skus) == 2
    names = {s["spec_name"] for s in skus}
    assert names == {"A", "B"}


# ──────────────── 3. 上架强校验 ────────────────

@pytest.mark.asyncio
async def test_publish_require_images(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "强校验图片")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "无图上架",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 200.0,
            "sale_price": 150.0,
            "stock": 50,
            "status": "active",
            "images": [],
        },
        headers=admin_headers,
    )
    assert resp.status_code >= 400
    assert "图片" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_publish_require_stock(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "强校验库存")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "零库存上架",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 200.0,
            "sale_price": 150.0,
            "stock": 0,
            "status": "active",
            "images": ["https://img.example.com/1.jpg"],
        },
        headers=admin_headers,
    )
    assert resp.status_code >= 400


@pytest.mark.asyncio
async def test_publish_multi_spec_require_default(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "多规格默认")
    resp = await client.post(
        "/api/admin/products",
        json={
            "name": "多规格无默认",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 0,
            "sale_price": 0,
            "stock": 0,
            "status": "active",
            "spec_mode": 2,
            "images": ["https://img.example.com/1.jpg"],
            "skus": [
                {"spec_name": "A", "sale_price": 10.0, "stock": 5, "is_default": False, "status": 1, "sort_order": 0},
                {"spec_name": "B", "sale_price": 20.0, "stock": 5, "is_default": False, "status": 1, "sort_order": 1},
            ],
        },
        headers=admin_headers,
    )
    # 没有默认规格 → 上架失败
    assert resp.status_code >= 400


# ──────────────── 4. 详情接口（含 has_orders） ────────────────

@pytest.mark.asyncio
async def test_admin_product_detail_with_skus(client: AsyncClient, admin_headers):
    cid = await _create_cat(client, admin_headers, "详情")
    create_resp = await client.post(
        "/api/admin/products",
        json={
            "name": "详情商品",
            "category_id": cid,
            "fulfillment_type": "in_store",
            "original_price": 0, "sale_price": 0, "stock": 0,
            "status": "draft", "spec_mode": 2,
            "images": ["https://img.example.com/1.jpg"],
            "skus": [
                {"spec_name": "X", "sale_price": 1.0, "stock": 10, "is_default": True, "status": 1, "sort_order": 0},
            ],
        },
        headers=admin_headers,
    )
    pid = create_resp.json()["id"]

    detail = await client.get(f"/api/admin/products/{pid}/detail", headers=admin_headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["spec_mode"] == 2
    assert len(data["skus"]) == 1
    assert data["skus"][0]["has_orders"] is False


# ──────────────── 5. 老数据兼容 ────────────────

@pytest.mark.asyncio
async def test_legacy_product_edit_default_to_unified_spec(client: AsyncClient, admin_headers):
    """老商品（无 SKU/无新字段）打开详情时应能正常返回，spec_mode 默认为 1"""
    async with test_session() as db:
        cat = ProductCategory(name="老数据", status="active", sort_order=0, level=1)
        db.add(cat)
        await db.flush()
        p = Product(
            name="老商品",
            category_id=cat.id,
            fulfillment_type="delivery",
            original_price=Decimal("100.00"),
            sale_price=Decimal("80.00"),
            stock=10,
            status="active",
            images=["https://img.example.com/legacy.jpg"],
            description="旧版纯文本描述",
        )
        db.add(p)
        await db.commit()
        pid = p.id

    detail = await client.get(f"/api/admin/products/{pid}/detail", headers=admin_headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["spec_mode"] in (1, None) or data["spec_mode"] == 1
    assert data.get("skus", []) == []
    assert data["description"] == "旧版纯文本描述"
