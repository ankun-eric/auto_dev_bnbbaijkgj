"""[PRD-TAG-RECOMMEND-V1 2026-05-20]
标签管理 / 商品标签 / 问卷推荐配置 / 问卷模板新字段 / Bug1 / 履约方式正名

测试覆盖：
- TC-01: 标签 CRUD（含同分类重名校验）
- TC-02: 标签合并（src 关联商品自动改到 target，src 删除）
- TC-03: 商品-标签关联读写（PUT /api/admin/goods/{id}/tags）
- TC-04: 问卷推荐配置保存（PUT /templates/{id}/recommend）
- TC-05: 问卷推荐配置预览（POST /recommend/preview）
- TC-06: 问卷模板 4 个新字段（result_display_mode / ai_followup_enabled / recommend_click_mode / recommend_display_count）保存往返
- TC-07: /api/questionnaire/submit 返回三段式新字段（recommend_goods / recommend_click_mode / result_display_mode）
- TC-08: 履约方式正名（virtual=权益服务 / delivery=实物配送，前端文件源码校验）
- TC-09: Bug1 - 关联问卷模板下拉 label 格式 + 加载失败提示（前端源码校验）
- TC-10: 9 种体质标签默认 seed（迁移脚本逻辑校验：通过 INITIAL_TAGS 常量检查）
- TC-11: 标签管理后台页面新建文件存在（前端源码校验）
- TC-12: H5 端推荐卡 + 商品详情抽屉组件新建（前端源码校验）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FulfillmentType,
    Product,
    ProductCategory,
    ProductStatus,
    QuestionnaireClassificationRule,
    QuestionnaireTemplate,
    Tag,
)


# ────────────────────────────── 路径解析 ──────────────────────────────
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


# ────────────────────────────── 通用工具 ──────────────────────────────


async def _setup_template_with_classifications(db_session):
    """在 DB 中插入一个测试用问卷模板 + 3 个分型"""
    tpl = QuestionnaireTemplate(
        code="test_tag_recommend",
        name="标签推荐测试问卷",
        result_display_mode="triple",
        ai_followup_enabled=True,
        recommend_click_mode="drawer",
        recommend_display_count=6,
    )
    db_session.add(tpl)
    await db_session.flush()
    for code, name in (("qi_xu", "气虚质"), ("yang_xu", "阳虚质"), ("ping_he", "平和质")):
        db_session.add(
            QuestionnaireClassificationRule(
                template_id=tpl.id,
                code=code,
                name=name,
                rule_type="dimension_max",
                rule_config={"dimension": code},
            )
        )
    await db_session.commit()
    return tpl


async def _seed_products(db_session, n: int = 5):
    """插入 n 个测试商品"""
    cat = ProductCategory(name="测试类目", sort_order=0)
    db_session.add(cat)
    await db_session.flush()
    prods = []
    for i in range(n):
        p = Product(
            name=f"测试商品{i+1}",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.delivery if i % 2 == 0 else FulfillmentType.virtual,
            sale_price=10 + i,
            original_price=20 + i,
            stock=100,
            sales_count=100 - i * 5,
            status=ProductStatus.active,
        )
        db_session.add(p)
        prods.append(p)
    await db_session.commit()
    return cat, prods


# ────────────────────────────── 测试 ──────────────────────────────


@pytest.mark.asyncio
async def test_tc01_tag_crud(client: AsyncClient, admin_headers, db_session):
    # 新增标签
    r = await client.post(
        "/api/admin/tags",
        json={"name": "补气", "category": "effect", "status": 1},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    # 同分类下重名应失败
    r2 = await client.post(
        "/api/admin/tags",
        json={"name": "补气", "category": "effect"},
        headers=admin_headers,
    )
    assert r2.status_code == 400

    # 不同分类下同名允许
    r3 = await client.post(
        "/api/admin/tags",
        json={"name": "补气", "category": "other"},
        headers=admin_headers,
    )
    assert r3.status_code == 200

    # 列表
    rl = await client.get("/api/admin/tags?category=effect", headers=admin_headers)
    assert rl.status_code == 200
    items = rl.json()["items"]
    assert any(t["name"] == "补气" for t in items)

    # 编辑
    ru = await client.put(
        f"/api/admin/tags/{tid}",
        json={"status": 0},
        headers=admin_headers,
    )
    assert ru.status_code == 200
    assert ru.json()["status"] == 0

    # 删除
    rd = await client.delete(f"/api/admin/tags/{tid}", headers=admin_headers)
    assert rd.status_code == 200


@pytest.mark.asyncio
async def test_tc02_tag_merge(client: AsyncClient, admin_headers, db_session):
    cat, prods = await _seed_products(db_session, 3)
    # 准备 src + target 标签
    r1 = await client.post(
        "/api/admin/tags",
        json={"name": "补气1", "category": "effect"},
        headers=admin_headers,
    )
    r2 = await client.post(
        "/api/admin/tags",
        json={"name": "补气2", "category": "effect"},
        headers=admin_headers,
    )
    src_id = r1.json()["id"]
    tgt_id = r2.json()["id"]
    # 给 2 个商品打 src 标签
    for p in prods[:2]:
        rs = await client.put(
            f"/api/admin/goods/{p.id}/tags",
            json={"tag_ids": [src_id]},
            headers=admin_headers,
        )
        assert rs.status_code == 200
    # 合并 src -> tgt
    rm = await client.post(
        f"/api/admin/tags/{src_id}/merge",
        json={"target_id": tgt_id},
        headers=admin_headers,
    )
    assert rm.status_code == 200, rm.text
    assert rm.json()["merged_goods"] == 2
    # src 已被删除
    src_row = await db_session.get(Tag, src_id)
    # session 缓存可能问题，重新查
    await db_session.commit()
    res = await db_session.execute(select(Tag).where(Tag.id == src_id))
    assert res.scalar_one_or_none() is None
    # tgt 应有 2 个商品
    rg = await client.get(f"/api/admin/tags/{tgt_id}/goods", headers=admin_headers)
    assert rg.status_code == 200
    assert rg.json()["total"] == 2


@pytest.mark.asyncio
async def test_tc03_goods_tags_rw(client: AsyncClient, admin_headers, db_session):
    cat, prods = await _seed_products(db_session, 1)
    gid = prods[0].id
    # 建标签
    rt = await client.post(
        "/api/admin/tags",
        json={"name": "气虚质", "category": "constitution"},
        headers=admin_headers,
    )
    tid = rt.json()["id"]

    # 写入关联
    r1 = await client.put(
        f"/api/admin/goods/{gid}/tags",
        json={"tag_ids": [tid]},
        headers=admin_headers,
    )
    assert r1.status_code == 200
    # 查询关联
    r2 = await client.get(f"/api/admin/goods/{gid}/tags", headers=admin_headers)
    assert r2.status_code == 200
    body = r2.json()
    assert tid in body["tag_ids"]
    assert any(t["name"] == "气虚质" for t in body["tags"])


@pytest.mark.asyncio
async def test_tc04_recommend_config_save(client: AsyncClient, admin_headers, db_session):
    tpl = await _setup_template_with_classifications(db_session)
    # 建几个标签
    rt = await client.post(
        "/api/admin/tags",
        json={"name": "补气", "category": "effect"},
        headers=admin_headers,
    )
    tag_id = rt.json()["id"]

    items = [
        {"result_key": "qi_xu", "mode": 2, "filter_json": {"tag_ids": [tag_id]}, "manual_goods_ids": None},
        {"result_key": "yang_xu", "mode": 3, "filter_json": None, "manual_goods_ids": [1, 2]},
    ]
    r = await client.put(
        f"/api/admin/questionnaire/templates/{tpl.id}/recommend",
        json={"items": items},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    # 读取回填
    rg = await client.get(
        f"/api/admin/questionnaire/templates/{tpl.id}/recommend",
        headers=admin_headers,
    )
    assert rg.status_code == 200
    body = rg.json()
    cfgs = {c["result_key"]: c for c in body["configs"]}
    assert "qi_xu" in cfgs and cfgs["qi_xu"]["mode"] == 2
    assert "yang_xu" in cfgs and cfgs["yang_xu"]["mode"] == 3


@pytest.mark.asyncio
async def test_tc05_recommend_preview(client: AsyncClient, admin_headers, db_session):
    tpl = await _setup_template_with_classifications(db_session)
    cat, prods = await _seed_products(db_session, 5)
    # 给前 3 个商品打个标签
    rt = await client.post(
        "/api/admin/tags",
        json={"name": "补气", "category": "effect"},
        headers=admin_headers,
    )
    tag_id = rt.json()["id"]
    for p in prods[:3]:
        await client.put(
            f"/api/admin/goods/{p.id}/tags",
            json={"tag_ids": [tag_id]},
            headers=admin_headers,
        )

    # 预览（按标签）
    r = await client.post(
        f"/api/admin/questionnaire/templates/{tpl.id}/recommend/preview",
        json={"result_key": "qi_xu", "mode": 2, "filter_json": {"tag_ids": [tag_id]}, "limit": 6},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    # 去重校验：商品ID唯一
    ids = [it["id"] for it in body["items"]]
    assert len(ids) == len(set(ids))
    # 字段校验
    if body["items"]:
        it = body["items"][0]
        assert "fulfillment_label" in it
        assert "sale_price" in it


@pytest.mark.asyncio
async def test_tc06_template_4_new_fields_roundtrip(client: AsyncClient, admin_headers, db_session):
    # 通过 admin 接口新建一个问卷模板，传入 4 个新字段
    r = await client.post(
        "/api/admin/questionnaire/templates",
        json={
            "code": "test_4_fields",
            "name": "测试模板",
            "result_display_mode": "triple",
            "ai_followup_enabled": True,
            "recommend_click_mode": "drawer",
            "recommend_display_count": 5,
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    tpl_id = r.json()["id"]
    # 查询回填
    rg = await client.get(
        f"/api/admin/questionnaire/templates/{tpl_id}",
        headers=admin_headers,
    )
    body = rg.json()
    assert body["result_display_mode"] == "triple"
    assert body["ai_followup_enabled"] is True
    assert body["recommend_click_mode"] == "drawer"
    assert body["recommend_display_count"] == 5
    # 修改成 external + count=4
    ru = await client.put(
        f"/api/admin/questionnaire/templates/{tpl_id}",
        json={"recommend_click_mode": "external", "recommend_display_count": 4},
        headers=admin_headers,
    )
    assert ru.status_code == 200
    assert ru.json()["recommend_click_mode"] == "external"
    assert ru.json()["recommend_display_count"] == 4


@pytest.mark.asyncio
async def test_tc07_submit_returns_triple_fields(client: AsyncClient, auth_headers, db_session):
    """问卷提交后返回 recommend_goods / result_display_mode / recommend_click_mode 新字段"""
    tpl = await _setup_template_with_classifications(db_session)
    cat, prods = await _seed_products(db_session, 3)
    # 提交一个空答案，主要校验返回结构
    r = await client.post(
        "/api/questionnaire/submit",
        json={"template_id": tpl.id, "answers": []},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "recommend_goods" in body
    assert "result_display_mode" in body
    assert "recommend_click_mode" in body
    assert "ai_followup_enabled" in body
    assert "recommend_display_count" in body
    assert body["result_display_mode"] == "triple"
    # recommend_goods 是 list（兜底销量 top）
    assert isinstance(body["recommend_goods"], list)


# ────────────────────────────── 前端源码校验 ──────────────────────────────


def test_tc08_fulfillment_label_renamed():
    """履约方式正名：virtual=权益服务 / delivery=实物配送"""
    for rel in (
        "admin-web/src/utils/fulfillmentLabel.ts",
        "h5-web/src/utils/fulfillmentLabel.ts",
    ):
        src = _read_text(rel)
        if src is None:
            pytest.skip(f"{rel} not found in current env")
            return
        assert "权益服务" in src, f"{rel} virtual -> 权益服务 文案未替换"
        assert "实物配送" in src, f"{rel} delivery -> 实物配送 文案未替换"
        # 旧文案不应作为 enum value 显示
        assert "'虚拟商品'" not in src, f"{rel} 旧文案「虚拟商品」残留"
        assert "'快递配送'" not in src, f"{rel} 旧文案「快递配送」残留"


def test_tc09_bug1_template_select_label_format():
    """Bug1：关联问卷模板下拉 label 格式 + 加载失败提示"""
    src = _read_text("admin-web/src/app/(admin)/function-buttons/page.tsx")
    if src is None:
        pytest.skip("admin-web function-buttons page not found")
        return
    # Label 格式应为 ${t.name}（${t.code}）
    assert "${t.name}（${t.code}）" in src, "Label 格式 ${t.name}（${t.code}）未实现"
    # 加载错误提示
    assert "questionnaireTplLoadError" in src, "加载错误状态字段未实现"
    assert "加载问卷模板失败" in src, "加载失败提示文案未找到"
    # 重新加载入口
    assert "data-testid=\"qn-tpl-reload-btn\"" in src or "qn-tpl-reload-btn" in src, "重试按钮 testid 未找到"


def test_tc10_constitution_tags_seed_in_migration():
    """迁移脚本中包含 9 种体质 seed 常量"""
    src = _read_text("backend/app/services/prd_tag_recommend_v1_migration.py")
    assert src is not None, "迁移脚本不存在"
    for name in ("平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质",
                 "湿热质", "血瘀质", "气郁质", "特禀质"):
        assert name in src, f"体质 seed 缺少 {name}"


def test_tc11_tags_admin_page_exists():
    """标签管理后台页面文件存在且包含 7 类 Tab"""
    src = _read_text("admin-web/src/app/(admin)/product-system/tags/page.tsx")
    assert src is not None, "标签管理页文件不存在"
    # 7 类
    for cat in ("symptom", "effect", "constitution", "crowd", "service", "scene", "other"):
        assert f"'{cat}'" in src or f'"{cat}"' in src, f"分类 {cat} 未在页面中"
    # 合并入口
    assert "合并" in src, "合并入口未找到"


def test_tc12_h5_recommend_components_exist():
    """H5 端推荐卡 + 商品详情抽屉组件 + ai-home 集成"""
    rec_src = _read_text("h5-web/src/components/ai-chat/QuestionnaireRecommendCard.tsx")
    drawer_src = _read_text("h5-web/src/components/ai-chat/RecommendGoodsDrawer.tsx")
    ai_home = _read_text("h5-web/src/app/(ai-chat)/ai-home/page.tsx")
    assert rec_src is not None, "QuestionnaireRecommendCard 组件不存在"
    assert drawer_src is not None, "RecommendGoodsDrawer 组件不存在"
    assert ai_home is not None
    assert "export default function QuestionnaireRecommendCard" in rec_src
    assert "export default function RecommendGoodsDrawer" in drawer_src
    # ai-home 引入
    assert "QuestionnaireRecommendCard" in ai_home, "ai-home 未引入推荐卡组件"
    assert "RecommendGoodsDrawer" in ai_home, "ai-home 未引入推荐商品抽屉组件"
    # questionnaire_recommend_card 消息类型
    assert "questionnaire_recommend_card" in ai_home, "questionnaire_recommend_card 消息 kind 未定义"
    # 抽屉状态
    assert "recommendDrawerOpen" in ai_home or "setRecommendDrawerOpen" in ai_home


def test_tc13_template_4_config_fields_in_admin_form():
    """admin 端问卷模板编辑页含有 4 个新配置项"""
    src = _read_text("admin-web/src/app/(admin)/questionnaire-templates/page.tsx")
    assert src is not None
    assert "result_display_mode" in src
    assert "ai_followup_enabled" in src
    assert "recommend_click_mode" in src
    assert "recommend_display_count" in src
    # 三段式选项
    assert "三段式" in src
    # external 警示
    assert "跳商城" in src
    assert "离开 AI 对话页" in src


def test_tc14_recommend_config_tab_in_drawer():
    """admin 端问卷模板抽屉内有「关联推荐」Tab + 3 种模式"""
    src = _read_text("admin-web/src/app/(admin)/questionnaire-templates/page.tsx")
    assert src is not None
    assert "关联推荐" in src
    assert "标签智能匹配" in src
    assert "按标签固定推荐" in src
    assert "手动挑商品" in src
    assert "预览推荐" in src
