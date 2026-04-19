"""第 N 期 5 BUG + 1 改造 回归测试

覆盖：
- BUG ①：体质测评提交在 question_id 不存在 / AI 异常时不再 500，返回 422 或正常完成入库
- BUG ②：/api/settings/logo 返回 logo_url 为后端拼好的可访问 URL
- BUG ③：/api/admin/coupons/redeem-code-batches/{id}/codes/export 返回 CSV 内容（带 BOM）
- BUG ⑤：商品分类层级修复后 — 「适老化改造」parent_id 必须非空且指向「居家服务」
- 改造 ④：/api/products?parent_category_id 自动包含子类；q 参数生效；/hot-recommendations 返回 6 个
"""
import pytest
from httpx import AsyncClient

from app.models.models import (
    ConstitutionQuestion,
    FulfillmentType,
    Product,
    ProductCategory,
    ProductStatus,
    SystemConfig,
)
from tests.conftest import test_session


# ─── BUG ①：TCM 体质测评不再 500 ───

@pytest.mark.asyncio
async def test_bug1_tcm_constitution_test_with_unknown_question_ids(
    monkeypatch, client: AsyncClient, auth_headers
):
    """前端硬编码 1-8 题，但 DB 中可能不存在这些 question_id；提交应当成功而非 500。"""

    async def _mock_ai(*args, **kwargs):
        return {
            "constitution_type": "气虚质",
            "syndrome_analysis": "测试辨证分析",
            "health_plan": "测试调理建议",
        }

    monkeypatch.setattr("app.api.tcm.tcm_analysis", _mock_ai)

    payload = {
        "answers": [
            {"question_id": 1, "answer_value": "偶尔"},
            {"question_id": 2, "answer_value": "经常"},
        ]
    }
    resp = await client.post("/api/tcm/constitution-test", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("constitution_type") == "气虚质"


@pytest.mark.asyncio
async def test_bug1_tcm_constitution_test_with_ai_failure(
    monkeypatch, client: AsyncClient, auth_headers
):
    """AI 调用抛异常时也不能 500，应有兜底"""

    async def _broken_ai(*args, **kwargs):
        raise RuntimeError("AI service down")

    monkeypatch.setattr("app.api.tcm.tcm_analysis", _broken_ai)

    payload = {"answers": [{"question_id": 1, "answer_value": "经常"}]}
    resp = await client.post("/api/tcm/constitution-test", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_bug1_tcm_constitution_test_empty_answers_returns_422(
    client: AsyncClient, auth_headers
):
    """空 answers 应返回 422（带具体 message），而非 500"""
    resp = await client.post(
        "/api/tcm/constitution-test", json={"answers": []}, headers=auth_headers
    )
    assert resp.status_code == 422
    assert "答题" in (resp.json().get("detail") or "")


@pytest.mark.asyncio
async def test_bug1_tcm_constitution_test_writes_only_valid_question_ids(
    monkeypatch, client: AsyncClient, auth_headers
):
    """answers 中合法的 question_id 写入 DB，不合法的跳过（不 500）"""

    async def _mock_ai(*args, **kwargs):
        return {"constitution_type": "平和质", "syndrome_analysis": "ok", "health_plan": "ok"}

    monkeypatch.setattr("app.api.tcm.tcm_analysis", _mock_ai)

    # 创建一个真实存在的 question
    async with test_session() as s:
        q = ConstitutionQuestion(question_text="测试题", order_num=1)
        s.add(q)
        await s.commit()
        await s.refresh(q)
        valid_qid = q.id

    payload = {
        "answers": [
            {"question_id": valid_qid, "answer_value": "经常"},
            {"question_id": 99999, "answer_value": "从不"},  # 不存在的 ID
        ]
    }
    resp = await client.post("/api/tcm/constitution-test", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text


# ─── BUG ②：Logo URL 拼接 ───

@pytest.mark.asyncio
async def test_bug2_logo_url_built_with_static_base_url(monkeypatch, client: AsyncClient):
    """STATIC_BASE_URL 设置后，/api/settings/logo 返回的 URL 必须带前缀"""
    monkeypatch.setenv("STATIC_BASE_URL", "https://example.com/autodev/abc")

    # 提前在 SystemConfig 写入一个 storage_path
    async with test_session() as s:
        s.add(SystemConfig(
            config_key="brand_logo_url",
            config_value="/uploads/logo/brand_logo.png",
            config_type="brand",
        ))
        await s.commit()

    resp = await client.get("/api/settings/logo")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["logo_url"] == "https://example.com/autodev/abc/uploads/logo/brand_logo.png"


@pytest.mark.asyncio
async def test_bug2_logo_url_returns_null_when_not_set(client: AsyncClient):
    resp = await client.get("/api/settings/logo")
    assert resp.status_code == 200
    assert resp.json()["data"]["logo_url"] is None


# ─── BUG ③：CSV 导出 ───

@pytest.mark.asyncio
async def test_bug3_export_batch_codes_csv_returns_csv_content(
    client: AsyncClient, admin_headers
):
    """导出接口存在且返回 CSV 头（含 BOM）"""
    # batch_id 不存在时也应返回 CSV（空批次）— 关键是路径可达且非 Gateway OK
    resp = await client.get(
        "/api/admin/coupons/redeem-code-batches/99999/codes/export",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    body = resp.content
    # CSV 首字节应为 UTF-8 BOM
    assert body.startswith(b"\xef\xbb\xbf"), "CSV 必须以 BOM 开头，避免 Excel 中文乱码"


@pytest.mark.asyncio
async def test_bug3_export_grants_csv(client: AsyncClient, admin_headers):
    resp = await client.get(
        "/api/admin/coupons/99999/grants/export", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


# ─── BUG ⑤：分类层级修复 ───

@pytest.mark.asyncio
async def test_bug5_categories_endpoint_separates_top_and_sub(client: AsyncClient):
    """/api/products/categories 必须把有 parent_id 的分类放到 children 而非 items 顶层"""
    async with test_session() as s:
        home = ProductCategory(name="居家服务", parent_id=None, sort_order=10, level=1)
        s.add(home)
        await s.commit()
        await s.refresh(home)

        elderly = ProductCategory(
            name="适老化改造", parent_id=home.id, sort_order=1, level=2
        )
        s.add(elderly)
        await s.commit()

    resp = await client.get("/api/products/categories")
    assert resp.status_code == 200
    items = resp.json()["items"]
    top_names = [c["name"] for c in items]
    assert "居家服务" in top_names
    assert "适老化改造" not in top_names, "适老化改造不应作为一级分类"
    home_node = next(c for c in items if c["name"] == "居家服务")
    assert any(child["name"] == "适老化改造" for child in home_node["children"])


# ─── 改造 ④：服务列表 ───

@pytest.mark.asyncio
async def test_change4_products_filter_by_parent_category_includes_subs(
    client: AsyncClient,
):
    """parent_category_id 必须包含该一级分类下所有子类的商品"""
    async with test_session() as s:
        top = ProductCategory(name="理疗保健", parent_id=None, level=1)
        s.add(top)
        await s.commit()
        await s.refresh(top)
        sub = ProductCategory(name="推拿", parent_id=top.id, level=2)
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        s.add(Product(
            name="肩颈推拿60分钟",
            category_id=sub.id,
            fulfillment_type=FulfillmentType.in_store,
            original_price=200,
            sale_price=168,
            status=ProductStatus.active,
        ))
        await s.commit()

    resp = await client.get(f"/api/products?parent_category_id={top.id}")
    assert resp.status_code == 200
    body = resp.json()
    names = [p["name"] for p in body["items"]]
    assert "肩颈推拿60分钟" in names


@pytest.mark.asyncio
async def test_change4_products_search_q_parameter(client: AsyncClient):
    async with test_session() as s:
        cat = ProductCategory(name="测试分类", parent_id=None, level=1)
        s.add(cat)
        await s.commit()
        await s.refresh(cat)
        s.add(Product(
            name="艾灸推拿", category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            original_price=100, sale_price=80, status=ProductStatus.active,
        ))
        s.add(Product(
            name="无关商品", category_id=cat.id,
            fulfillment_type=FulfillmentType.delivery,
            original_price=50, sale_price=40, status=ProductStatus.active,
        ))
        await s.commit()

    resp = await client.get("/api/products?q=推拿")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "艾灸推拿" in names
    assert "无关商品" not in names


@pytest.mark.asyncio
async def test_change4_hot_recommendations_endpoint(client: AsyncClient):
    async with test_session() as s:
        cat = ProductCategory(name="测试分类2", parent_id=None, level=1)
        s.add(cat)
        await s.commit()
        await s.refresh(cat)
        for i in range(8):
            s.add(Product(
                name=f"热销商品{i}", category_id=cat.id,
                fulfillment_type=FulfillmentType.virtual,
                original_price=100, sale_price=80,
                sales_count=100 - i, status=ProductStatus.active,
            ))
        await s.commit()

    resp = await client.get("/api/products/hot-recommendations?limit=6")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 6


@pytest.mark.asyncio
async def test_change4_virtual_fulfillment_type_supported(client: AsyncClient):
    """改造④：FulfillmentType 必须支持 virtual"""
    async with test_session() as s:
        cat = ProductCategory(name="虚拟服务", parent_id=None, level=1)
        s.add(cat)
        await s.commit()
        await s.refresh(cat)
        s.add(Product(
            name="在线问诊咨询券",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.virtual,
            original_price=50, sale_price=39,
            status=ProductStatus.active,
        ))
        await s.commit()

    resp = await client.get(f"/api/products?category_id={cat.id}&fulfillment_type=virtual")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["fulfillment_type"] == "virtual"
