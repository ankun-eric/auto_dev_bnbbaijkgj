"""[实物商品与积分商城彻底解耦 v1.0 2026-05-25] 验收测试

PRD：实物商品与积分商城彻底解耦 v1.0
- 商品编辑页【会员与积分】Tab 不再出现"是否进入积分商城"与"积分商城兑换所需积分"
- 后端接口（创建/编辑/详情/列表）不再返回上述两个字段
- 老版本客户端如传入这两个字段，后端忽略且不报错（兼容一个发版周期）
- 数据库列保留物理列（按 PRD 回滚策略），但业务层永远写入默认值
- 积分商城与积分抵扣订单金额、付费会员折扣等其它玩法完全不受影响

本文件采用与现有 test_product_system.py 相同的 sqlite+aiosqlite 内存库测试范式。
"""

import pytest
from httpx import AsyncClient

from app.models.models import Product, ProductCategory
from tests.conftest import test_session


async def _seed_category(name: str = "解耦测试分类") -> int:
    async with test_session() as db:
        cat = ProductCategory(
            name=name, status="active", sort_order=0, level=1, parent_id=None,
        )
        db.add(cat)
        await db.commit()
        return cat.id


async def _seed_product(category_id: int, *, name: str = "测试商品") -> int:
    async with test_session() as db:
        product = Product(
            name=name,
            category_id=category_id,
            fulfillment_type="delivery",
            original_price=199.0,
            sale_price=99.0,
            images=["https://img.example.com/1.jpg"],
            stock=100,
            status="active",
            redeem_count=1,
            appointment_mode="none",
        )
        db.add(product)
        await db.commit()
        return product.id


# ─────────────────────────────────────────────────────────────
# T1：商品列表响应体不再含 points_exchangeable / points_price
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t1_list_response_no_points_mall_fields(client: AsyncClient):
    cat_id = await _seed_category()
    await _seed_product(cat_id, name="解耦商品A")

    resp = await client.get("/api/products")
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "points_exchangeable" not in item, (
            f"商品列表响应不应再含 points_exchangeable 字段，实际：{item.keys()}"
        )
        assert "points_price" not in item, (
            f"商品列表响应不应再含 points_price 字段，实际：{item.keys()}"
        )
        # 解耦后保留的字段（付费会员折扣 + 积分抵扣订单）仍应存在
        assert "points_deductible" in item, "积分抵扣订单字段必须保留"
        assert "is_member_discount_eligible" in item, "付费会员折扣字段必须保留"


# ─────────────────────────────────────────────────────────────
# T2：商品详情响应体不再含 points_exchangeable / points_price
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t2_detail_response_no_points_mall_fields(client: AsyncClient):
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, name="详情商品")

    resp = await client.get(f"/api/products/{pid}")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["id"] == pid
    assert "points_exchangeable" not in data, (
        f"商品详情响应不应再含 points_exchangeable 字段，实际 keys：{list(data.keys())}"
    )
    assert "points_price" not in data, (
        f"商品详情响应不应再含 points_price 字段，实际 keys：{list(data.keys())}"
    )
    # 保留字段
    assert "points_deductible" in data
    assert "is_member_discount_eligible" in data


# ─────────────────────────────────────────────────────────────
# T3：列表接口忽略 points_exchangeable 查询参数（兼容老客户端）
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t3_list_ignores_legacy_points_exchangeable_param(client: AsyncClient):
    cat_id = await _seed_category()
    await _seed_product(cat_id, name="实物A")
    await _seed_product(cat_id, name="实物B")

    # 老 H5/小程序/App 可能仍传 points_exchangeable=true，后端应忽略并返回全部
    resp_true = await client.get("/api/products", params={"points_exchangeable": True})
    assert resp_true.status_code == 200, resp_true.text
    data_true = resp_true.json()
    assert data_true["total"] == 2, "传入老参数应被忽略，返回全部商品"

    resp_false = await client.get("/api/products", params={"points_exchangeable": False})
    assert resp_false.status_code == 200, resp_false.text
    data_false = resp_false.json()
    assert data_false["total"] == 2, "传入老参数应被忽略，返回全部商品"


# ─────────────────────────────────────────────────────────────
# T4：后台创建商品接口接收旧字段时不报错（兼容老客户端发版周期）
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t4_admin_create_product_ignores_legacy_fields(
    client: AsyncClient, admin_headers
):
    cat_id = await _seed_category()

    # 老版本管理后台请求体可能仍带 points_exchangeable / points_price
    payload = {
        "name": "兼容老入参的商品",
        "category_id": cat_id,
        "fulfillment_type": "delivery",
        "sale_price": 88.0,
        "original_price": 188.0,
        "stock": 50,
        "redeem_count": 1,
        "appointment_mode": "none",
        # 老字段（必须被忽略）
        "points_exchangeable": True,
        "points_price": 1000,
        # 保留字段
        "points_deductible": True,
        "is_member_discount_eligible": True,
        "status": "draft",
    }

    resp = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    # 后端必须忽略两个老字段并返回成功，老版本客户端不应被打挂
    assert resp.status_code in (200, 201), f"老入参兼容失败：{resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("name") == "兼容老入参的商品"

    # 创建后的商品在 DB 中 points_exchangeable 应仍为默认值 False、points_price 为 0
    async with test_session() as db:
        from sqlalchemy import select as sql_select
        result = await db.execute(
            sql_select(Product).where(Product.name == "兼容老入参的商品")
        )
        product = result.scalar_one()
        assert bool(product.points_exchangeable) is False, (
            "解耦后老入参 points_exchangeable=True 必须被忽略，DB 中应仍为 False"
        )
        assert int(product.points_price or 0) == 0, (
            "解耦后老入参 points_price=1000 必须被忽略，DB 中应仍为 0"
        )
        # 解耦不影响 points_deductible / is_member_discount_eligible
        assert bool(product.points_deductible) is True
        assert bool(product.is_member_discount_eligible) is True


# ─────────────────────────────────────────────────────────────
# T5：后台编辑商品接口接收旧字段时不报错且不写库（兼容老客户端）
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t5_admin_update_product_ignores_legacy_fields(
    client: AsyncClient, admin_headers
):
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, name="待更新商品")

    # 老前端发起编辑，仍可能带这两个字段
    payload = {
        "points_exchangeable": True,
        "points_price": 500,
        "name": "更新后的名字",
    }
    resp = await client.put(
        f"/api/admin/products/{pid}", json=payload, headers=admin_headers
    )
    assert resp.status_code == 200, f"老入参编辑兼容失败：{resp.status_code} {resp.text}"

    # 校验 DB：名字更新成功，但 points_* 仍为默认值
    async with test_session() as db:
        from sqlalchemy import select as sql_select
        result = await db.execute(sql_select(Product).where(Product.id == pid))
        product = result.scalar_one()
        assert product.name == "更新后的名字"
        assert bool(product.points_exchangeable) is False
        assert int(product.points_price or 0) == 0


# ─────────────────────────────────────────────────────────────
# T6：后台商品详情接口响应不再含两个字段
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t6_admin_product_detail_no_points_mall_fields(
    client: AsyncClient, admin_headers
):
    cat_id = await _seed_category()
    pid = await _seed_product(cat_id, name="后台详情商品")

    resp = await client.get(
        f"/api/admin/products/{pid}/detail", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("id") == pid
    assert "points_exchangeable" not in data, (
        f"后台商品详情响应不应再含 points_exchangeable 字段，实际 keys：{list(data.keys())}"
    )
    assert "points_price" not in data, (
        f"后台商品详情响应不应再含 points_price 字段，实际 keys：{list(data.keys())}"
    )
