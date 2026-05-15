"""[PRD-AICHAT-CAPSULE-V2 2026-05-15] AI 咨询配置-功能按钮管理优化 非UI 自动化测试

覆盖：
  N1. PromptTemplate 模型新字段 code / is_builtin 持久化
  N2. /api/admin/prompt-templates/all/flat 返回内置模板优先排序
  N3. /api/admin/prompt-templates/{id}/duplicate 复制内置模板生成副本（is_builtin=0, code=None, name+"（副本）"）
  N4. 复制非内置模板被拒绝（400）
  N5. /api/admin/prompt-templates/by-id/{id} 单条获取，包含 code/is_builtin 字段
  N6. /api/admin/function-buttons 接受 card_cover_image 字段（兼容旧前端传入）
  N7. /api/admin/function-buttons 不带 card_cover_image 字段也能正常创建/读取（PRD 需求 2）
  N8. /api/admin/function-buttons 仍接受 ai_reply_mode 字段（向后兼容，但功能上不再被使用）
  N9. ChatFunctionButtonResponse Schema 含 prompt_template_id 字段（PRD 需求 3 关联模板）
  N10. 内置模板迁移函数：能将 reply_mode='full' 等映射到对应 prompt_template_id
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import ChatFunctionButton, PromptTemplate


@pytest_asyncio.fixture
async def builtin_templates(db_session):
    """预置 3 个系统内置识药模板（模拟启动期迁移效果，给后续测试用）。"""
    builtins = []
    for code, name, prompt_type in [
        ("MED_RECOG_FULL", "识药-完整分析", "drug_personal"),
        ("MED_RECOG_ADVICE_ONLY", "识药-仅用药建议", "drug_general"),
        ("MED_RECOG_AUTO", "识药-AI 自动判断", "drug_query"),
    ]:
        t = PromptTemplate(
            name=name,
            prompt_type=prompt_type,
            content=f"内置 {code} 模板内容（测试用）",
            version=1,
            is_active=False,
            code=code,
            is_builtin=True,
        )
        db_session.add(t)
        builtins.append(t)
    await db_session.commit()
    return {t.code: t.id for t in builtins}


# ─────────────────── N1 ───────────────────
@pytest.mark.asyncio
async def test_prompt_template_model_has_code_and_is_builtin(db_session):
    """PromptTemplate 模型可正常持久化 code/is_builtin。"""
    t = PromptTemplate(
        name="x",
        prompt_type="drug_general",
        content="c",
        version=1,
        is_active=False,
        code="TEST_CODE",
        is_builtin=True,
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    assert t.code == "TEST_CODE"
    assert t.is_builtin is True


# ─────────────────── N2 ───────────────────
@pytest.mark.asyncio
async def test_list_all_flat_returns_builtin_first(
    client: AsyncClient, admin_headers, builtin_templates, db_session
):
    # 再插一条非内置模板
    t = PromptTemplate(
        name="自建模板",
        prompt_type="drug_general",
        content="user content",
        version=1,
        is_active=False,
        code=None,
        is_builtin=False,
    )
    db_session.add(t)
    await db_session.commit()

    res = await client.get("/api/admin/prompt-templates/all/flat", headers=admin_headers)
    assert res.status_code == 200, res.text
    items = res.json()
    assert len(items) >= 4
    # 内置必须在前
    builtin_count = 0
    for it in items[:3]:
        assert it["is_builtin"] is True, f"前 3 条应全部是内置，但出现非内置：{it}"
        builtin_count += 1
    assert builtin_count == 3
    codes = {it["code"] for it in items if it["is_builtin"]}
    assert {"MED_RECOG_FULL", "MED_RECOG_ADVICE_ONLY", "MED_RECOG_AUTO"} <= codes


# ─────────────────── N3 ───────────────────
@pytest.mark.asyncio
async def test_duplicate_builtin_template_creates_copy(
    client: AsyncClient, admin_headers, builtin_templates
):
    src_id = builtin_templates["MED_RECOG_FULL"]
    res = await client.post(
        f"/api/admin/prompt-templates/{src_id}/duplicate", headers=admin_headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_builtin"] is False
    assert data["code"] in (None, "")
    assert "副本" in data["name"]
    # 副本是新 id
    assert data["id"] != src_id


# ─────────────────── N4 ───────────────────
@pytest.mark.asyncio
async def test_duplicate_non_builtin_template_rejected(
    client: AsyncClient, admin_headers, db_session
):
    t = PromptTemplate(
        name="某用户自建",
        prompt_type="drug_general",
        content="c",
        version=1,
        is_active=True,
        code=None,
        is_builtin=False,
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)

    res = await client.post(
        f"/api/admin/prompt-templates/{t.id}/duplicate", headers=admin_headers
    )
    assert res.status_code == 400
    assert "内置" in res.json().get("detail", "")


# ─────────────────── N5 ───────────────────
@pytest.mark.asyncio
async def test_get_template_by_id_includes_new_fields(
    client: AsyncClient, admin_headers, builtin_templates
):
    src_id = builtin_templates["MED_RECOG_AUTO"]
    res = await client.get(f"/api/admin/prompt-templates/by-id/{src_id}", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == src_id
    assert data["is_builtin"] is True
    assert data["code"] == "MED_RECOG_AUTO"


# ─────────────────── N6 ───────────────────
@pytest.mark.asyncio
async def test_function_button_create_accepts_legacy_cover_url(
    client: AsyncClient, admin_headers
):
    """老前端可能仍传 card_cover_image，后端需接受不报错（PRD 需求 2 兼容）。"""
    payload = {
        "name": "拍照识药",
        "icon": "💊",
        "button_type": "photo_recognize_drug",
        "sort_weight": 10,
        "is_enabled": True,
        "card_cover_image": "https://example.com/cover.png",  # 旧字段
        "auto_user_message": "拍照识药",
        "card_title": "拍照识药",
    }
    res = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "拍照识药"


# ─────────────────── N7 ───────────────────
@pytest.mark.asyncio
async def test_function_button_create_without_cover_url(
    client: AsyncClient, admin_headers
):
    """不传 card_cover_image 也能创建（PRD 需求 2 移除该字段）。"""
    payload = {
        "name": "快捷提问",
        "icon": "⚡",
        "button_type": "quick_ask",
        "sort_weight": 5,
        "is_enabled": True,
        "preset_prompt": "我想了解高血压日常注意事项",
        "auto_user_message": "我想了解高血压日常注意事项",
        "card_title": "高血压咨询",
    }
    res = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["preset_prompt"] == "我想了解高血压日常注意事项"


# ─────────────────── N8 ───────────────────
@pytest.mark.asyncio
async def test_function_button_create_with_legacy_reply_mode(
    client: AsyncClient, admin_headers
):
    """老前端可能仍传 ai_reply_mode，后端需接受不报错（PRD 需求 3 向后兼容）。"""
    payload = {
        "name": "拍照识药",
        "icon": "💊",
        "button_type": "photo_recognize_drug",
        "sort_weight": 10,
        "is_enabled": True,
        "ai_reply_mode": "complete_analysis",
        "auto_user_message": "拍照识药",
        "card_title": "拍照识药",
    }
    res = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert res.status_code == 200, res.text


# ─────────────────── N9 ───────────────────
@pytest.mark.asyncio
async def test_function_button_response_has_prompt_template_id_field(
    client: AsyncClient, admin_headers, builtin_templates
):
    payload = {
        "name": "拍照识药",
        "icon": "💊",
        "button_type": "photo_recognize_drug",
        "sort_weight": 10,
        "is_enabled": True,
        "prompt_template_id": builtin_templates["MED_RECOG_FULL"],
        "auto_user_message": "拍照识药",
        "card_title": "拍照识药",
    }
    res = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["prompt_template_id"] == builtin_templates["MED_RECOG_FULL"]


# ─────────────────── N10 ───────────────────
@pytest.mark.asyncio
async def test_reply_mode_to_template_code_mapping():
    """单元层校验：映射表覆盖所有 PRD 规定的旧值。"""
    from app.services.prd_aichat_capsule_v2_migration import REPLY_MODE_TO_CODE
    assert REPLY_MODE_TO_CODE["full"] == "MED_RECOG_FULL"
    assert REPLY_MODE_TO_CODE["complete_analysis"] == "MED_RECOG_FULL"
    assert REPLY_MODE_TO_CODE["medicine_only"] == "MED_RECOG_ADVICE_ONLY"
    assert REPLY_MODE_TO_CODE["basic_advice"] == "MED_RECOG_ADVICE_ONLY"
    assert REPLY_MODE_TO_CODE["auto"] == "MED_RECOG_AUTO"
    assert REPLY_MODE_TO_CODE["ai_auto"] == "MED_RECOG_AUTO"
    assert REPLY_MODE_TO_CODE[""] == "MED_RECOG_AUTO"
    assert REPLY_MODE_TO_CODE[None] == "MED_RECOG_AUTO"


# ─────────────────── N11：公开接口仍返回胶囊数据 ───────────────────
@pytest.mark.asyncio
async def test_public_function_buttons_endpoint(client: AsyncClient, admin_headers):
    """PRD 需求 4：胶囊数据源 /api/function-buttons 仍可正常返回，且按 sort_weight 升序。"""
    # 准备两条按钮，sort_weight 顺序不同
    for sw, name, btype in [
        (20, "B按钮", "quick_ask"),
        (10, "A按钮", "photo_recognize_drug"),
    ]:
        payload = {
            "name": name,
            "icon": "📌",
            "button_type": btype,
            "sort_weight": sw,
            "is_enabled": True,
            "preset_prompt": "test" if btype == "quick_ask" else None,
            "auto_user_message": name,
            "card_title": name,
        }
        await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)

    res = await client.get("/api/function-buttons")
    assert res.status_code == 200, res.text
    items = res.json()
    assert len(items) >= 2
    # sort_weight 升序
    sws = [it["sort_weight"] for it in items]
    assert sws == sorted(sws)
