"""Tests for BUG FIX: 商品原价(original_price)为空时显示 0

原始 Bug：新建商品不填写原价字段时，保存后原价被存储为 0（而非 NULL），
导致管理后台编辑时显示 0。

修复内容：
- Product 模型 original_price 改为 nullable=True
- Schema 改为 Optional[float] = None
- API 返回处理 None（而非 0）

覆盖用例：
1. 不传 original_price → API 返回 None（复现 Bug）
2. 传 original_price=null → 存储和返回均为 None（复现 Bug）
3. 更新商品将 original_price 设为 null → 清除成功
4. 传 original_price=99.99 → 正常存储和返回
5. ProductResponse 能正确序列化 original_price=None
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import Product, ProductCategory
from app.schemas.products import ProductResponse
from tests.conftest import test_session


async def _create_cat(client: AsyncClient, admin_headers, name="原价测试分类") -> int:
    resp = await client.post(
        "/api/admin/products/categories",
        json={"name": name, "status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


_BASE_PRODUCT = {
    "name": "原价测试商品",
    "fulfillment_type": "in_store",
    "sale_price": 99.0,
    "stock": 50,
    "status": "draft",
}


# ══════════════════════════════════════════════════════
#  1. 复现 Bug 的测试（修复前应失败，修复后应通过）
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_product_without_original_price(client: AsyncClient, admin_headers):
    """创建商品不传 original_price，验证 API 返回中 original_price 为 None（而非 0）"""
    cid = await _create_cat(client, admin_headers, "不传原价分类")
    resp = await client.post(
        "/api/admin/products",
        json={**_BASE_PRODUCT, "category_id": cid},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["original_price"] is None, (
        f"Bug 复现：original_price 应为 None，实际为 {data['original_price']}"
    )


@pytest.mark.asyncio
async def test_create_product_with_null_original_price(client: AsyncClient, admin_headers):
    """创建商品显式传 original_price=null，验证存储和返回都为 None"""
    cid = await _create_cat(client, admin_headers, "传null原价分类")
    resp = await client.post(
        "/api/admin/products",
        json={**_BASE_PRODUCT, "category_id": cid, "original_price": None},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["original_price"] is None, (
        f"Bug 复现：original_price 应为 None，实际为 {data['original_price']}"
    )

    # 验证数据库实际存储的值也是 NULL
    pid = data["id"]
    async with test_session() as db:
        result = await db.execute(select(Product).where(Product.id == pid))
        product = result.scalar_one()
        assert product.original_price is None, (
            f"数据库中 original_price 应为 NULL，实际为 {product.original_price}"
        )


@pytest.mark.asyncio
async def test_update_product_clear_original_price(client: AsyncClient, admin_headers):
    """更新商品将 original_price 设为 null，验证清除成功"""
    cid = await _create_cat(client, admin_headers, "清除原价分类")

    # 先创建一个有原价的商品
    create_resp = await client.post(
        "/api/admin/products",
        json={**_BASE_PRODUCT, "category_id": cid, "original_price": 199.0},
        headers=admin_headers,
    )
    assert create_resp.status_code == 200
    pid = create_resp.json()["id"]
    assert create_resp.json()["original_price"] == 199.0

    # 更新时将 original_price 设为 null
    update_resp = await client.put(
        f"/api/admin/products/{pid}",
        json={"original_price": None},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["original_price"] is None, (
        f"清除原价失败：应为 None，实际为 {update_resp.json()['original_price']}"
    )

    # 再次获取详情确认持久化
    detail_resp = await client.get(
        f"/api/admin/products/{pid}/detail",
        headers=admin_headers,
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["original_price"] is None


# ══════════════════════════════════════════════════════
#  2. 边界情况测试
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_product_with_original_price(client: AsyncClient, admin_headers):
    """创建商品传 original_price=99.99，验证正常存储和返回"""
    cid = await _create_cat(client, admin_headers, "有原价分类")
    resp = await client.post(
        "/api/admin/products",
        json={**_BASE_PRODUCT, "category_id": cid, "original_price": 99.99},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["original_price"] == 99.99

    # 验证数据库存储
    pid = data["id"]
    async with test_session() as db:
        result = await db.execute(select(Product).where(Product.id == pid))
        product = result.scalar_one()
        assert float(product.original_price) == 99.99


@pytest.mark.asyncio
async def test_product_response_schema_allows_null_original_price(client: AsyncClient, admin_headers):
    """验证 ProductResponse 可以正确序列化 original_price=None"""
    cid = await _create_cat(client, admin_headers, "schema序列化分类")

    # 直接通过 ORM 创建一个 original_price=NULL 的商品
    async with test_session() as db:
        cat_result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == cid)
        )
        cat = cat_result.scalar_one()
        product = Product(
            name="Schema测试商品",
            category_id=cat.id,
            fulfillment_type="in_store",
            original_price=None,
            sale_price=50.0,
            stock=10,
            status="draft",
            images=["https://img.example.com/test.jpg"],
            appointment_mode="none",
        )
        db.add(product)
        await db.commit()
        pid = product.id

    # 通过 C 端详情接口获取
    resp = await client.get(f"/api/products/{pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_price"] is None, (
        f"C 端详情 original_price 应为 None，实际为 {data['original_price']}"
    )

    # 通过管理后台详情接口获取
    detail_resp = await client.get(
        f"/api/admin/products/{pid}/detail",
        headers=admin_headers,
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["original_price"] is None, (
        f"管理后台详情 original_price 应为 None，实际为 {detail_resp.json()['original_price']}"
    )

    # 通过管理后台列表接口获取
    list_resp = await client.get(
        "/api/admin/products",
        params={"keyword": "Schema测试商品"},
        headers=admin_headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) >= 1
    target = next(i for i in items if i["id"] == pid)
    assert target["original_price"] is None
