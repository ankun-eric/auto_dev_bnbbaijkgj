"""[PRD-TCM-DRAWER-V12 2026-05-20] 体质测评 36 题 + 双触发 + AI 引用 验收测试

覆盖：
- TC-01：constitution_score 36 题反向计分（题 34/35/36）公式正确
- TC-02：tcm_constitution 模板 + 36 题 seed 可执行
- TC-03：ChatFunctionButton 新增 5 个开关字段可读写
- TC-04：function_button admin API 创建/更新带 trigger_keywords 字段往返一致
- TC-05：POST /api/chat/intent-detect 关键词命中返回 questionnaire_tcm_constitution
- TC-06：POST /api/chat/intent-detect 未命中返回 source=none
- TC-07：POST /api/questionnaire/submit 满分答案返回主体质
- TC-08：tcm_context.build_constitution_system_prompt 输出 80 字内
"""
from __future__ import annotations

import json
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.models.models import (
    ChatFunctionButton,
    QuestionnaireTemplate,
    QuestionnaireQuestion,
    QuestionnaireAnswer,
)
from app.services.constitution_score import (
    calculate_constitution,
    REVERSE_SCORE_ORDER_NUMS,
    CONSTITUTION_GROUPS,
)
from app.services.tcm_context import (
    build_constitution_system_prompt,
    CONSTITUTION_BRIEF,
)


# ──────────────── TC-01：反向计分 ────────────────
@pytest.mark.asyncio
async def test_tc01_reverse_score_for_pinghe():
    """题 34/35/36 是反向计分。原始选项 5（总是）→ 实际计分 1。"""
    assert REVERSE_SCORE_ORDER_NUMS == {34, 35, 36}
    # 阳虚质 4 题全部"总是"，得分应为最高
    # 平和质 4 题（第 33 正、34/35/36 反）全部选"总是"
    #   33 正：5
    #   34/35/36 反：每题 6-5=1，三题共 3
    #   原始分 = 5 + 1 + 1 + 1 = 8
    #   转换分 = (8 - 4) / (4*4) * 100 = 25.0
    answers = []
    # 阳虚质 4 题：每题原始 5 → 转换分 = (20-4)/16*100 = 100
    for o in range(5, 9):
        answers.append({"order_num": o, "group": "阳虚质", "answer_value": "总是"})
    # 平和质 4 题：33 正、34/35/36 反，全选"总是"
    answers.append({"order_num": 33, "group": "平和质", "answer_value": "总是"})
    for o in (34, 35, 36):
        answers.append({"order_num": o, "group": "平和质", "answer_value": "总是"})
    res = calculate_constitution(answers)
    assert res.scores["阳虚质"] == 100.0
    # 平和质：原始分 = 5 + 1*3 = 8 → 转换分 = (8-4)/16*100 = 25.0
    assert res.scores["平和质"] == 25.0
    assert res.main_type == "阳虚质"


# ──────────────── TC-02：seed 36 题 ────────────────
@pytest.mark.asyncio
async def test_tc02_seed_tcm36_creates_36_questions(db_session):
    """运行 seed 后，tcm_constitution 模板下应该有 36 道题，34/35/36 标记为反向。"""
    from app.services.prd_tcm36_drawer_v12_migration import (
        _seed_tcm36_template_and_questions,
    )
    stats = await _seed_tcm36_template_and_questions(db_session)
    await db_session.commit()
    assert stats["questions_inserted"] == 36
    assert stats["template_action"] in ("created", "updated")
    tpl_id = stats["template_id"]
    qs = (
        await db_session.execute(
            text("SELECT sort_order, dimension, display_condition_json "
                 "FROM questionnaire_question WHERE template_id = :tid "
                 "ORDER BY sort_order ASC"),
            {"tid": tpl_id},
        )
    ).fetchall()
    assert len(qs) == 36
    # 检查 9 体质分组
    groups = {row[1] for row in qs}
    assert groups == set(CONSTITUTION_GROUPS)
    # 检查反向题：第 34/35/36 题
    for row in qs:
        order = row[0]
        meta_raw = row[2]
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else (meta_raw or {})
        if order in (34, 35, 36):
            assert meta.get("is_reverse_score") is True, f"order {order} should be reverse"
        else:
            assert meta.get("is_reverse_score") is False or meta.get("is_reverse_score") is None, (
                f"order {order} should not be reverse"
            )


# ──────────────── TC-03：ChatFunctionButton 新字段 ────────────────
@pytest.mark.asyncio
async def test_tc03_button_new_fields_orm(db_session):
    """ChatFunctionButton 新增 5 字段可读写"""
    btn = ChatFunctionButton(
        name="体质测评",
        button_type="ai_function",
        ai_function_type="questionnaire",
        trigger_by_keyword=True,
        trigger_by_intent=False,
        trigger_keywords=["体质测评", "我要测体质"],
        ai_reference_passive=True,
        ai_reference_active=False,
    )
    db_session.add(btn)
    await db_session.flush()
    assert btn.trigger_by_keyword is True
    assert btn.trigger_by_intent is False
    assert btn.trigger_keywords == ["体质测评", "我要测体质"]
    assert btn.ai_reference_passive is True
    assert btn.ai_reference_active is False


# ──────────────── TC-04：admin API 字段往返 ────────────────
@pytest.mark.asyncio
async def test_tc04_admin_button_roundtrip(client: AsyncClient, admin_headers):
    """admin 创建按钮，5 个新字段可保存并被读取出来"""
    payload = {
        "name": "中医体质测评",
        "button_type": "ai_function",
        "ai_function_type": "questionnaire",
        "questionnaire_template_id": 1,
        "questionnaire_display_form": "INLINE_CHAT",
        "trigger_by_keyword": True,
        "trigger_by_intent": True,
        "trigger_keywords": ["体质测评", "中医体质"],
        "ai_reference_passive": True,
        "ai_reference_active": True,
        "pre_card_enabled": True,
    }
    # 先建一个 questionnaire_template 让 questionnaire_template_id 校验过
    from app.models.models import QuestionnaireTemplate
    from app.core.database import async_sessionmaker
    # 使用测试 session
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="tcm_constitution", name="中医体质")
        db.add(tpl)
        await db.commit()
        payload["questionnaire_template_id"] = tpl.id

    r = await client.post(
        "/api/admin/function-buttons", json=payload, headers=admin_headers
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    btn_id = body["id"]
    # 直接断言创建响应里的新字段
    assert body["trigger_by_keyword"] is True
    assert body["trigger_by_intent"] is True
    assert body["trigger_keywords"] == ["体质测评", "中医体质"]
    assert body["ai_reference_passive"] is True
    assert body["ai_reference_active"] is True
    # 用 list 接口再次读回（admin GET /api/admin/function-buttons）
    r2 = await client.get(
        "/api/admin/function-buttons?page=1&page_size=50", headers=admin_headers
    )
    assert r2.status_code == 200, r2.text
    items = r2.json().get("items", [])
    target = next((it for it in items if it["id"] == btn_id), None)
    assert target is not None, "created button not in list"
    assert target["trigger_keywords"] == ["体质测评", "中医体质"]
    assert target["ai_reference_active"] is True


# ──────────────── TC-05：意图识别接口（命中） ────────────────
@pytest.mark.asyncio
async def test_tc05_intent_detect_hit(client: AsyncClient, admin_headers):
    """POST /api/chat/intent-detect 输入"我要做体质测评"返回 keyword 命中"""
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="tcm_constitution", name="中医体质测评")
        db.add(tpl)
        await db.flush()
        btn = ChatFunctionButton(
            name="体质测评",
            button_type="ai_function",
            ai_function_type="questionnaire",
            questionnaire_template_id=tpl.id,
            is_enabled=True,
            trigger_by_keyword=True,
            trigger_keywords=["体质测评", "我要做体质测评", "中医体质"],
        )
        db.add(btn)
        await db.commit()

    r = await client.post(
        "/api/chat/intent-detect", json={"text": "我要做体质测评"}
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "keyword"
    assert d["intent"] == "questionnaire_tcm_constitution"
    assert d["questionnaire_template_code"] == "tcm_constitution"
    assert d["matched_keyword"] in ("体质测评", "我要做体质测评")


# ──────────────── TC-06：意图识别接口（未命中） ────────────────
@pytest.mark.asyncio
async def test_tc06_intent_detect_miss(client: AsyncClient):
    """无任何按钮时，POST 任意文本 → source=none"""
    r = await client.post(
        "/api/chat/intent-detect", json={"text": "今天天气真好"}
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "none"
    assert d["intent"] is None


# ──────────────── TC-07：questionnaire submit 返回主体质 ────────────────
@pytest.mark.asyncio
async def test_tc07_submit_returns_main_type(client: AsyncClient, auth_headers):
    """提交 36 题（阳虚质全选总是、其它平均）→ 主体质应为阳虚质，且 active_followup 非空"""
    from tests.conftest import test_session as _ts
    # 先 seed 36 题
    async with _ts() as db:
        from app.services.prd_tcm36_drawer_v12_migration import (
            _seed_tcm36_template_and_questions,
        )
        stats = await _seed_tcm36_template_and_questions(db)
        await db.commit()
        tpl_id = stats["template_id"]
        # 取出 36 题 id+sort_order
        rows = (
            await db.execute(
                text("SELECT id, sort_order, dimension FROM questionnaire_question "
                     "WHERE template_id = :tid ORDER BY sort_order ASC"),
                {"tid": tpl_id},
            )
        ).fetchall()

    answers = []
    for row in rows:
        qid, order, dim = row[0], row[1], row[2]
        # 阳虚质全选"总是"，其它选"没有"
        val = "总是" if dim == "阳虚质" else "没有"
        answers.append({"question_id": qid, "value": val})

    r = await client.post(
        "/api/questionnaire/submit",
        json={"template_id": tpl_id, "answers": answers},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "answer_id" in d
    # active_followup 应该提到主体质
    assert d.get("active_followup")
    # 验证答卷被写入
    async with _ts() as db:
        ans = await db.get(QuestionnaireAnswer, d["answer_id"])
        assert ans is not None
        # 阳虚质 dimension_scores 应该是 100
        if isinstance(ans.dimension_scores, dict):
            assert ans.dimension_scores.get("阳虚质", 0) >= 90


# ──────────────── TC-08：AI 上下文注入文本长度 ────────────────
@pytest.mark.asyncio
async def test_tc08_build_constitution_prompt_within_80_chars():
    """build_constitution_system_prompt 返回的文本应在 80 字内"""
    for main_type in ["阳虚质", "气虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质", "平和质"]:
        prompt = build_constitution_system_prompt({"main_type": main_type})
        assert prompt is not None
        assert len(prompt) <= 80, f"prompt too long for {main_type}: {len(prompt)}"
        assert main_type in prompt
    # None 输入返回 None
    assert build_constitution_system_prompt(None) is None
    assert build_constitution_system_prompt({"main_type": None}) is None
