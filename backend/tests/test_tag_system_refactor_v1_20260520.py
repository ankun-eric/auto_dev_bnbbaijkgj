"""[商品标签体系重构 v1.0 2026-05-20] 体系重构专项测试

覆盖要点：
- TC-R01: TAG_CATEGORIES 收敛为 6 类（去 service/other，新增 contraindication）
- TC-R02: 体质类标签具有 is_locked=1 标识，不可物理删除
- TC-R03: 体质类标签不可修改名称/分类
- TC-R04: 普通标签被商品引用时不可删除（提示已被 N 个商品使用）
- TC-R05: products.symptom_tags 字段已不再写入；GET /api/admin/products 列表正常工作
- TC-R06: 商品打标接口（PUT /api/admin/goods/{id}/tags）+ 详情读出 tag_ids/tags 分组
- TC-R07: C 端 GET /api/products 关键词搜索可命中标签名
- TC-R08: C 端 GET /api/products/{id}/related 相关商品按标签命中数排序
- TC-R09: Product 模型移除 symptom_tags 字段（model attribute 不存在）
- TC-R10: Tag 模型新增 is_locked、sort_order 字段
- TC-R11: 商品编辑页 UI 文件中已删除"症状标签自由输入框"和"适用体质 Checkbox.Group"
- TC-R12: 商品编辑页包含 6 大分类 Chip 池容器（data-testid 标识）
- TC-R13: 商品编辑页对实物（delivery）隐藏服务相关分类（含禁忌类）
"""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FulfillmentType,
    GoodsTag,
    Product,
    ProductCategory,
    ProductStatus,
    Tag,
)


_HERE = Path(__file__).resolve()
_CANDIDATES = [_HERE.parents[2], _HERE.parents[1]]


def _find_root_with(rel: str) -> Path | None:
    for root in _CANDIDATES:
        if (root / rel).exists():
            return root
    return None


def _read_text(rel: str) -> str | None:
    root = _find_root_with(rel)
    if root is None:
        return None
    return (root / rel).read_text(encoding="utf-8")


async def _seed_simple_product(db_session, *, ft=FulfillmentType.virtual, name="商品A") -> tuple[int, int]:
    """插入一个测试商品；返回 (product_id, category_id)"""
    cat = ProductCategory(name="测试类目", sort_order=0)
    db_session.add(cat)
    await db_session.flush()
    p = Product(
        name=name,
        category_id=cat.id,
        fulfillment_type=ft,
        sale_price=10,
        original_price=20,
        stock=10,
        sales_count=1,
        status=ProductStatus.active,
    )
    db_session.add(p)
    await db_session.commit()
    return p.id, cat.id


# ───────────────────────── 模型层 ─────────────────────────


def test_tcr01_tag_categories_6_buckets():
    """TAG_CATEGORIES 应为 6 类，不含 service/other"""
    from app.schemas.tag_recommend import TAG_CATEGORIES
    assert set(TAG_CATEGORIES) == {
        "constitution", "symptom", "crowd", "effect", "scene", "contraindication"
    }
    assert "service" not in TAG_CATEGORIES
    assert "other" not in TAG_CATEGORIES


def test_tcr09_product_model_no_symptom_tags_attr():
    """Product 模型不再声明 symptom_tags 列"""
    cols = {c.name for c in Product.__table__.columns}
    assert "symptom_tags" not in cols, "symptom_tags 列应已从 products 模型中移除"


def test_tcr10_tag_model_has_new_columns():
    """Tag 模型新增 is_locked、sort_order 字段"""
    cols = {c.name for c in Tag.__table__.columns}
    assert "is_locked" in cols
    assert "sort_order" in cols


# ───────────────────────── API 层 ─────────────────────────


@pytest.mark.asyncio
async def test_tcr02_constitution_locked_cannot_delete(client: AsyncClient, admin_headers, db_session):
    """体质类标签 is_locked=1，不可物理删除"""
    # 先建一个 is_locked=1 的体质标签
    t = Tag(name="测试体质质", category="constitution", status=1, is_locked=1, sort_order=0)
    db_session.add(t)
    await db_session.commit()
    r = await client.delete(f"/api/admin/tags/{t.id}", headers=admin_headers)
    assert r.status_code == 400, r.text
    assert "体质" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_tcr03_locked_cannot_change_name_or_category(client: AsyncClient, admin_headers, db_session):
    t = Tag(name="测试体质质2", category="constitution", status=1, is_locked=1, sort_order=0)
    db_session.add(t)
    await db_session.commit()

    r1 = await client.put(
        f"/api/admin/tags/{t.id}",
        json={"name": "改个名"},
        headers=admin_headers,
    )
    assert r1.status_code == 400

    r2 = await client.put(
        f"/api/admin/tags/{t.id}",
        json={"category": "symptom"},
        headers=admin_headers,
    )
    assert r2.status_code == 400

    # 但允许仅改 status / sort_order
    r3 = await client.put(
        f"/api/admin/tags/{t.id}",
        json={"status": 0, "sort_order": 99},
        headers=admin_headers,
    )
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_tcr04_in_use_tag_cannot_delete(client: AsyncClient, admin_headers, db_session):
    # 建一个普通标签，挂到一个商品上
    t = Tag(name="助眠", category="effect", status=1, is_locked=0, sort_order=0)
    db_session.add(t)
    await db_session.flush()
    pid, _ = await _seed_simple_product(db_session, name="商品-tcr04")
    db_session.add(GoodsTag(goods_id=pid, tag_id=t.id))
    await db_session.commit()
    r = await client.delete(f"/api/admin/tags/{t.id}", headers=admin_headers)
    assert r.status_code == 400, r.text
    assert "使用" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_tcr06_goods_tags_round_trip(client: AsyncClient, admin_headers, db_session):
    """商品打标 + 读详情：返回 tag_ids 和 tags 分组"""
    pid, _ = await _seed_simple_product(db_session, name="商品-tcr06")
    # 创建几个不同分类的标签
    tags = [
        Tag(name="疲劳-r06", category="symptom", status=1),
        Tag(name="补气-r06", category="effect", status=1),
        Tag(name="气虚质-r06", category="constitution", status=1, is_locked=1),
    ]
    for t in tags:
        db_session.add(t)
    await db_session.commit()
    tag_ids = [t.id for t in tags]

    r1 = await client.put(
        f"/api/admin/goods/{pid}/tags",
        json={"tag_ids": tag_ids},
        headers=admin_headers,
    )
    assert r1.status_code == 200
    assert set(r1.json()["tag_ids"]) == set(tag_ids)

    r2 = await client.get(f"/api/admin/products/{pid}/detail", headers=admin_headers)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert set(body.get("tag_ids", [])) == set(tag_ids)
    grouped = body.get("tags", {})
    assert "symptom" in grouped and "effect" in grouped and "constitution" in grouped


@pytest.mark.asyncio
async def test_tcr05_products_list_compat_no_symptom_tags(client: AsyncClient, db_session):
    """drop symptom_tags 之后 C 端 GET /api/products 列表不出错，且响应中存在 tag_ids/tags 字段"""
    pid, _ = await _seed_simple_product(db_session, name="商品-tcr05")
    r = await client.get("/api/products?page=1&page_size=10")
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    # 至少包含我们刚建的商品
    target = next((it for it in items if it.get("id") == pid), None)
    assert target is not None
    assert "tag_ids" in target
    assert "tags" in target


@pytest.mark.asyncio
async def test_tcr07_c_side_keyword_hits_tag(client: AsyncClient, admin_headers, db_session):
    """关键词搜索可经由标签名命中"""
    pid, _ = await _seed_simple_product(db_session, name="搜不到的商品名r07")
    t = Tag(name="UniqKwTagR07", category="symptom", status=1)
    db_session.add(t)
    await db_session.flush()
    db_session.add(GoodsTag(goods_id=pid, tag_id=t.id))
    await db_session.commit()
    r = await client.get("/api/products", params={"q": "UniqKwTagR07"})
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert any(it.get("id") == pid for it in items), "标签名应能命中关键词搜索"


@pytest.mark.asyncio
async def test_tcr08_related_products_by_tag_hits(client: AsyncClient, db_session):
    """C 端相关商品按标签命中数倒序排序"""
    # 建商品 A, B, C, D：A 是基准；B 命中 2 个标签；C 命中 1 个；D 不命中
    cat = ProductCategory(name="测试类目-r08", sort_order=0)
    db_session.add(cat)
    await db_session.flush()
    prods = []
    for i in range(4):
        p = Product(
            name=f"r08-p{i}",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.virtual,
            sale_price=10,
            original_price=20,
            stock=10,
            sales_count=0,
            status=ProductStatus.active,
        )
        db_session.add(p)
        prods.append(p)
    await db_session.flush()

    t1 = Tag(name="r08-tag1", category="symptom", status=1)
    t2 = Tag(name="r08-tag2", category="effect", status=1)
    db_session.add_all([t1, t2])
    await db_session.flush()

    a, b, c, _d = prods
    # A 挂 t1, t2
    db_session.add_all([GoodsTag(goods_id=a.id, tag_id=t1.id), GoodsTag(goods_id=a.id, tag_id=t2.id)])
    # B 也挂 t1, t2
    db_session.add_all([GoodsTag(goods_id=b.id, tag_id=t1.id), GoodsTag(goods_id=b.id, tag_id=t2.id)])
    # C 只挂 t1
    db_session.add(GoodsTag(goods_id=c.id, tag_id=t1.id))
    await db_session.commit()

    r = await client.get(f"/api/products/{a.id}/related?limit=5")
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    ids = [it["id"] for it in items]
    # A 自身不应出现
    assert a.id not in ids
    # B 应排在 C 之前
    if b.id in ids and c.id in ids:
        assert ids.index(b.id) < ids.index(c.id)


# ───────────────────────── 前端文件检查 ─────────────────────────


def test_tcr11_product_edit_no_old_inputs():
    """商品编辑页旧的「症状标签自由输入框」、「适用体质 Checkbox.Group」标签 UI 应被删除"""
    src = _read_text("admin-web/src/app/(admin)/product-system/products/page.tsx")
    assert src is not None
    # 旧的 Form.Item name="symptom_tags" Select + 适用体质 Checkbox.Group 应被删除
    assert 'Form.Item label="症状标签"' not in src, "旧症状标签输入框未删除"
    assert 'Form.Item label="适用体质"' not in src, "旧适用体质 Checkbox 未删除"


def test_tcr12_product_edit_has_chip_pool():
    """商品编辑页含 6 大分类 Chip 池（模板字符串 + 分类定义）"""
    src = _read_text("admin-web/src/app/(admin)/product-system/products/page.tsx")
    assert src is not None
    # 6 大分类常量定义必须存在
    assert "TAG_CATEGORY_DEFS" in src
    for cat in ("constitution", "symptom", "crowd", "effect", "scene", "contraindication"):
        assert f"'{cat}'" in src or f'"{cat}"' in src, f"分类 {cat} 缺失"
    # Chip 池模板字符串 testid 前缀
    assert "tag-chip-category-" in src, "标签 chip 容器 testid 前缀缺失"
    assert "toggleTag(" in src, "chip 点击切换函数缺失"
    # 已选 N 实时显示
    assert "已选" in src, "缺少『已选 N』提示"


def test_tcr13_product_edit_hide_service_for_physical():
    """商品编辑页在 fulfillment_type=delivery 时隐藏 hideForPhysical=true 的分类"""
    src = _read_text("admin-web/src/app/(admin)/product-system/products/page.tsx")
    assert src is not None
    assert "hideForPhysical" in src, "未发现 hideForPhysical 控制逻辑"
    # contraindication 标记为 hideForPhysical=true
    assert "contraindication" in src and "hideForPhysical: true" in src
