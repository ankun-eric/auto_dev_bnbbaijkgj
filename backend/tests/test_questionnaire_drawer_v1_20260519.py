"""[PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]
健康自查抽屉化 + 新版问卷模板体系融合 后端测试。

覆盖范围：
1. ChatFunctionButton 新增 questionnaire_display_form 字段可读写 + 校验
2. QuestionnaireTemplate 新增 result_summary_template / source 字段可读写
3. QuestionnaireQuestion 新增 display_condition_json / option_filter_json / layout_hint 字段可读写
4. /api/questionnaire/buttons/{button_id}/render-meta 返回完整渲染元信息
5. /api/questionnaire/submit 提交后返回结果卡片结构 + 摘要文案
6. result_summary_template 占位符替换正确
7. ai_function_type=questionnaire 校验 questionnaire_display_form 枚举合法
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.api.function_button import ALLOWED_QUESTIONNAIRE_DISPLAY_FORMS
from app.models.models import (
    ChatFunctionButton,
    QuestionnaireQuestion,
    QuestionnaireTemplate,
)


@pytest.mark.asyncio
async def test_display_form_enum_three():
    """问卷展示形态枚举必须恰好 3 个。"""
    assert ALLOWED_QUESTIONNAIRE_DISPLAY_FORMS == {
        "DRAWER_SCROLL",
        "DRAWER_STEPPED",
        "INLINE_CHAT",
    }


@pytest.mark.asyncio
async def test_template_new_fields_orm(db_session):
    """questionnaire_template 新字段可写入读取。"""
    tpl = QuestionnaireTemplate(
        code="t_drawer_demo",
        name="抽屉化测试模板",
        result_summary_template="部位：{部位} | 症状：{症状}",
        source="system_migrated",
    )
    db_session.add(tpl)
    await db_session.flush()
    assert tpl.result_summary_template.startswith("部位：")
    assert tpl.source == "system_migrated"


@pytest.mark.asyncio
async def test_question_new_fields_orm(db_session):
    """questionnaire_question 联动字段可写入读取。"""
    tpl = QuestionnaireTemplate(code="t_qfields", name="题目字段测试")
    db_session.add(tpl)
    await db_session.flush()
    q = QuestionnaireQuestion(
        template_id=tpl.id,
        sort_order=1,
        question_type="multi_choice",
        title="症状（联动测试）",
        options=[{"label": "头痛", "value": "headache"}, {"label": "胸闷", "value": "chest"}],
        dimension="症状",
        display_condition_json={"deps": [{"question_dimension": "部位", "operator": "not_empty"}]},
        option_filter_json={
            "deps": [{"question_dimension": "部位", "operator": "in"}],
            "filter_map": {"头部": ["headache"], "胸部": ["chest"]},
            "default": [],
        },
        layout_hint="tag_list",
    )
    db_session.add(q)
    await db_session.flush()
    assert q.display_condition_json["deps"][0]["operator"] == "not_empty"
    assert q.option_filter_json["filter_map"]["头部"] == ["headache"]
    assert q.layout_hint == "tag_list"


@pytest_asyncio.fixture
async def seed_drawer_template(db_session):
    """造一份完整健康自查问卷模板，3 道题（部位/症状/持续时间）+ 联动。"""
    tpl = QuestionnaireTemplate(
        code=f"hsc_drawer_test",
        name="健康自查（抽屉化测试）",
        result_summary_template="部位：{部位} | 症状：{症状} | 持续：{持续时间}",
        ai_opening="正在分析…",
        source="system_migrated",
    )
    db_session.add(tpl)
    await db_session.flush()
    q1 = QuestionnaireQuestion(
        template_id=tpl.id,
        sort_order=1,
        question_type="multi_choice",
        title="请选择不适部位",
        options=[
            {"label": "头部", "value": "头部", "icon": "🧠"},
            {"label": "胸部", "value": "胸部", "icon": "🫁"},
        ],
        dimension="部位",
        layout_hint="icon_grid",
    )
    q2 = QuestionnaireQuestion(
        template_id=tpl.id,
        sort_order=2,
        question_type="multi_choice",
        title="请选择症状",
        options=[
            {"label": "头痛", "value": "头痛"},
            {"label": "头晕", "value": "头晕"},
            {"label": "胸闷", "value": "胸闷"},
        ],
        dimension="症状",
        display_condition_json={
            "deps": [{"question_dimension": "部位", "operator": "not_empty"}],
        },
        option_filter_json={
            "deps": [{"question_dimension": "部位", "operator": "in"}],
            "filter_map": {"头部": ["头痛", "头晕"], "胸部": ["胸闷"]},
            "default": [],
        },
        layout_hint="tag_list",
    )
    q3 = QuestionnaireQuestion(
        template_id=tpl.id,
        sort_order=3,
        question_type="single_choice",
        title="持续了多久？",
        options=[
            {"label": "今天", "value": "今天"},
            {"label": "3 天", "value": "3 天"},
        ],
        dimension="持续时间",
    )
    db_session.add_all([q1, q2, q3])
    await db_session.commit()
    return {"template_id": tpl.id, "q1": q1.id, "q2": q2.id, "q3": q3.id}


@pytest_asyncio.fixture
async def seed_button(db_session, seed_drawer_template):
    """造一个绑定该模板、形态=DRAWER_SCROLL 的 AI 功能按钮。"""
    btn = ChatFunctionButton(
        name="健康自查（测试）",
        icon="🩺",
        button_type="ai_function",
        ai_function_type="questionnaire",
        questionnaire_template_id=seed_drawer_template["template_id"],
        questionnaire_display_form="DRAWER_SCROLL",
        is_enabled=True,
        is_recommended=True,
        sort_weight=10,
        card_title="",
        auto_user_message="",
    )
    db_session.add(btn)
    await db_session.commit()
    return {"button_id": btn.id, **seed_drawer_template}


@pytest.mark.asyncio
async def test_render_meta(client: AsyncClient, seed_button):
    """render-meta 接口返回完整元信息，含 display_form / template / questions（带联动字段）。"""
    btn_id = seed_button["button_id"]
    resp = await client.get(f"/api/questionnaire/buttons/{btn_id}/render-meta")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_form"] == "DRAWER_SCROLL"
    assert body["button"]["id"] == btn_id
    assert body["template"]["code"].startswith("hsc_drawer_test")
    assert body["template"]["result_summary_template"]
    assert body["template"]["source"] == "system_migrated"
    qs = body["questions"]
    assert len(qs) == 3
    # 第 2 题应该带有联动字段
    q2 = next(q for q in qs if q["dimension"] == "症状")
    assert q2["display_condition_json"]
    assert q2["option_filter_json"]["filter_map"]["头部"] == ["头痛", "头晕"]
    assert q2["layout_hint"] == "tag_list"


@pytest.mark.asyncio
async def test_submit_returns_card(client: AsyncClient, auth_headers, seed_drawer_template):
    """/api/questionnaire/submit 返回结果卡片结构 + 摘要文案（占位符替换正确）。"""
    tpl_id = seed_drawer_template["template_id"]
    payload = {
        "template_id": tpl_id,
        "answers": [
            {"question_id": seed_drawer_template["q1"], "value": ["头部"]},
            {"question_id": seed_drawer_template["q2"], "value": ["头痛", "头晕"]},
            {"question_id": seed_drawer_template["q3"], "value": "3 天"},
        ],
    }
    resp = await client.post(
        "/api/questionnaire/submit", headers=auth_headers, json=payload
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer_id"]
    card = body["card"]
    assert card["template_code"].startswith("hsc_drawer_test")
    # 摘要文案中的占位符应该被替换
    assert card["summary_text"] == "部位：头部 | 症状：头痛、头晕 | 持续：3 天"
    fields = {f["label"]: f["value"] for f in card["fields"]}
    assert fields["部位"] == "头部"
    assert fields["症状"] == "头痛、头晕"
    assert fields["持续时间"] == "3 天"


@pytest.mark.asyncio
async def test_display_form_validation_in_create(
    client: AsyncClient, admin_headers, seed_drawer_template
):
    """创建按钮时，questionnaire 子类型的 display_form 必须是合法枚举值。"""
    tpl_id = seed_drawer_template["template_id"]
    # 1. 合法值
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "测试按钮 ok",
            "button_type": "ai_function",
            "ai_function_type": "questionnaire",
            "questionnaire_template_id": tpl_id,
            "questionnaire_display_form": "DRAWER_STEPPED",
            "is_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["questionnaire_display_form"] == "DRAWER_STEPPED"

    # 2. 非法值应该 400
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "测试按钮 bad",
            "button_type": "ai_function",
            "ai_function_type": "questionnaire",
            "questionnaire_template_id": tpl_id,
            "questionnaire_display_form": "INVALID_FORM",
            "is_enabled": True,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_display_form_inline_chat_acceptable(
    client: AsyncClient, admin_headers, seed_drawer_template
):
    """INLINE_CHAT 也是合法值。"""
    tpl_id = seed_drawer_template["template_id"]
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "测试 inline 按钮",
            "button_type": "ai_function",
            "ai_function_type": "questionnaire",
            "questionnaire_template_id": tpl_id,
            "questionnaire_display_form": "INLINE_CHAT",
            "is_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["questionnaire_display_form"] == "INLINE_CHAT"
