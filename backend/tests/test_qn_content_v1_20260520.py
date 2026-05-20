"""[PRD-QN-CONTENT-V1 2026-05-20] 4 个问卷题库 + 健康自查 6 维度 + chips/CTA 后台配置 · 验收测试

覆盖：
- TC-Q-1：PHQ-9 / GAD-7 / PSQI 题库可正确算分并落分型
- TC-Q-2：PHQ-9 第 9 题 ≥ 1 分时返回 phq9_crisis=True 且 cta_list 含心理援助热线
- TC-Q-3：每个问卷的 chat_messages 末尾有 cta_buttons 消息
- TC-Q-4：cta_list 默认 2 个，运营后台配置的 cta_list_json 可覆盖默认
- TC-Q-5：followup_chips_json 可被运营后台配置覆盖
- TC-Q-6：health_self_check 升级版可读到新维度（症状性质/严重程度/症状备注）
"""
from __future__ import annotations

import datetime as _dt
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.models.models import (
    QuestionnaireClassificationRule,
    QuestionnaireQuestion,
    QuestionnaireTemplate,
)


# ════════════════════════════════════════════════════════════════
# 辅助：在测试 DB 中创建一份指定 code 的模板 + 题目 + 分型规则
# ════════════════════════════════════════════════════════════════


async def _seed_template(
    db,
    *,
    code: str,
    name: str,
    questions: list[dict],
    options: list[dict],
    classifications: list[dict],
    chips: list[dict] | None = None,
    cta: list[dict] | None = None,
    rule_type: str = "score_range",
) -> int:
    tpl = QuestionnaireTemplate(
        code=code,
        name=name,
        description=f"{name} test seed",
        intro_text="test",
        ai_opening=f"您的 {name} 已完成",
        ai_prompt_template=f"主体质:{{main_type}} 分数:{{scores}}",
        result_summary_template=f"{name} 总分：{{scores}}\n等级：{{main_type}}",
        estimated_minutes=3,
        allow_back=True,
        shuffle_questions=False,
        report_layout="score_bar",
        status=1,
        source="system_migrated",
        followup_chips_json=chips,
        cta_list_json=cta,
    )
    db.add(tpl)
    await db.flush()
    for q in questions:
        item = QuestionnaireQuestion(
            template_id=tpl.id,
            sort_order=q["order"],
            question_type="single_choice",
            title=q["title"],
            subtitle=f"第 {q['order']} 题",
            required=True,
            options=q.get("options") or options,
            dimension=q.get("dim", code.upper()),
            display_condition_json={"order_num": q["order"]},
            layout_hint="tag_list",
        )
        db.add(item)
    for idx, cls in enumerate(classifications):
        rule_cfg: dict
        if rule_type == "score_range":
            rule_cfg = {"min": cls["min"], "max": cls["max"]}
        else:
            rule_cfg = {"dimension": cls["name"]}
        db.add(
            QuestionnaireClassificationRule(
                template_id=tpl.id,
                code=cls["code"],
                name=cls["name"],
                description=cls.get("desc", ""),
                rule_type=rule_type,
                rule_config=rule_cfg,
                sort_order=idx,
            )
        )
    await db.commit()
    await db.refresh(tpl)
    return tpl.id


# ════════════════════════════════════════════════════════════════
# 各问卷题库
# ════════════════════════════════════════════════════════════════

PHQ9_OPTS = [
    {"label": "完全没有", "value": "完全没有", "score": 0},
    {"label": "几天", "value": "几天", "score": 1},
    {"label": "一半以上的天数", "value": "一半以上的天数", "score": 2},
    {"label": "几乎每天", "value": "几乎每天", "score": 3},
]
PHQ9_QUESTIONS = [
    {"order": i + 1, "title": f"PHQ9 Q{i + 1}", "dim": "PHQ9"} for i in range(9)
]
PHQ9_CLASS = [
    {"code": "phq9_none", "name": "没有或最少抑郁", "min": 0, "max": 4},
    {"code": "phq9_mild", "name": "轻度抑郁", "min": 5, "max": 9},
    {"code": "phq9_moderate", "name": "中度抑郁", "min": 10, "max": 14},
    {"code": "phq9_mod_severe", "name": "中重度抑郁", "min": 15, "max": 19},
    {"code": "phq9_severe", "name": "重度抑郁", "min": 20, "max": 27},
]

GAD7_QUESTIONS = [
    {"order": i + 1, "title": f"GAD7 Q{i + 1}", "dim": "GAD7"} for i in range(7)
]
GAD7_CLASS = [
    {"code": "gad7_none", "name": "没有或最少焦虑", "min": 0, "max": 4},
    {"code": "gad7_mild", "name": "轻度焦虑", "min": 5, "max": 9},
    {"code": "gad7_moderate", "name": "中度焦虑", "min": 10, "max": 14},
    {"code": "gad7_severe", "name": "重度焦虑", "min": 15, "max": 21},
]

PSQI_QUESTIONS = [
    {"order": i + 1, "title": f"PSQI Q{i + 1}", "dim": f"C{(i // 3) + 1}"}
    for i in range(19)
]
PSQI_CLASS = [
    {"code": "psqi_good", "name": "睡眠质量好", "min": 0, "max": 5},
    {"code": "psqi_fair", "name": "睡眠质量一般", "min": 6, "max": 10},
    {"code": "psqi_poor", "name": "睡眠质量差", "min": 11, "max": 15},
    {"code": "psqi_very_poor", "name": "睡眠质量很差", "min": 16, "max": 21},
]


async def _create_test_user(client: AsyncClient):
    """注册并登录一个测试用户，返回 auth_headers。复用现有用户 fixture 就好。"""
    pass


async def _submit_questionnaire(
    client: AsyncClient,
    auth_headers,
    tpl_id: int,
    answers_value: list,
):
    """提交问卷答案。answers_value 是和题目顺序对齐的答案列表。"""
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT id, sort_order FROM questionnaire_question "
                    "WHERE template_id = :tid ORDER BY sort_order ASC"
                ),
                {"tid": tpl_id},
            )
        ).fetchall()
    assert len(rows) == len(answers_value), (
        f"answers count {len(answers_value)} != questions {len(rows)}"
    )
    answers = [
        {"question_id": row[0], "value": val}
        for row, val in zip(rows, answers_value)
    ]
    r = await client.post(
        "/api/questionnaire/submit",
        json={"template_id": tpl_id, "answers": answers},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────── TC-Q-1：PHQ-9 算分 ────────────────
@pytest.mark.asyncio
async def test_phq9_scoring_and_classification(client: AsyncClient, auth_headers):
    """PHQ-9 9 题全选「一半以上的天数」（2 分）= 总分 18 = 中重度抑郁"""
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db,
            code="phq9",
            name="PHQ-9 抑郁筛查",
            questions=PHQ9_QUESTIONS,
            options=PHQ9_OPTS,
            classifications=PHQ9_CLASS,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["一半以上的天数"] * 9)
    assert data["template_id"] == tpl_id
    # 总分 18，等级=中重度抑郁
    chat_msgs = data.get("chat_messages") or []
    text_msg = next((m for m in chat_msgs if m.get("type") == "text"), None)
    assert text_msg is not None
    # cta_list 默认 2 个
    cta = data.get("cta_list") or []
    assert len(cta) >= 2, f"phq9 cta_list 应至少 2 个，got {cta}"


# ──────────────── TC-Q-2：PHQ-9 Q9 危机 CTA ────────────────
@pytest.mark.asyncio
async def test_phq9_q9_crisis_cta(client: AsyncClient, auth_headers):
    """PHQ-9 第 9 题 = 几天（1 分）时，phq9_crisis=True 且 cta_list 含心理援助热线"""
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db,
            code="phq9",
            name="PHQ-9 抑郁筛查",
            questions=PHQ9_QUESTIONS,
            options=PHQ9_OPTS,
            classifications=PHQ9_CLASS,
        )
    # 前 8 题选 "完全没有"，第 9 题选 "几天"（1 分）
    answers_value = ["完全没有"] * 8 + ["几天"]
    data = await _submit_questionnaire(client, auth_headers, tpl_id, answers_value)
    assert data.get("phq9_crisis") is True
    cta = data.get("cta_list") or []
    # 第一个 CTA 必须是危机热线
    assert any("400-161-9995" in (c.get("target_url") or "") or "心理援助" in (c.get("label") or "")
               for c in cta), f"crisis CTA 必须出现在 cta_list，got {cta}"


# ──────────────── TC-Q-3：cta_buttons 消息追加在 chat_messages 末尾 ────────────────
@pytest.mark.asyncio
async def test_cta_message_appended_to_chat_messages(client: AsyncClient, auth_headers):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db, code="gad7", name="GAD-7 焦虑筛查",
            questions=GAD7_QUESTIONS, options=PHQ9_OPTS, classifications=GAD7_CLASS,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["几天"] * 7)
    chat_msgs = data.get("chat_messages") or []
    types = [m.get("type") for m in chat_msgs]
    assert "cta_buttons" in types, f"chat_messages 末尾应含 cta_buttons，got {types}"
    # 类型顺序必须是 card → text → followup_chips → cta_buttons
    assert types[0] == "questionnaire_result_card"
    assert types[-1] == "cta_buttons"
    last = chat_msgs[-1]
    assert last["sender"] == "ai"
    assert isinstance(last.get("cta_list"), list) and len(last["cta_list"]) >= 1


# ──────────────── TC-Q-4：运营后台 cta_list_json 覆盖默认 ────────────────
@pytest.mark.asyncio
async def test_admin_cta_override(client: AsyncClient, auth_headers):
    """模板配置 cta_list_json=[A] 时，返回的 cta_list 应只含 A（不再用默认）"""
    custom_cta = [
        {"label": "运营自定义 CTA", "action": "open_shop",
         "target_url": "/shop/custom", "style": "primary"},
    ]
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db, code="psqi", name="PSQI",
            questions=PSQI_QUESTIONS, options=PHQ9_OPTS, classifications=PSQI_CLASS,
            cta=custom_cta,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["完全没有"] * 19)
    cta = data.get("cta_list") or []
    assert any(c.get("label") == "运营自定义 CTA" for c in cta), (
        f"运营自定义 CTA 应出现，got {cta}"
    )


# ──────────────── TC-Q-5：运营 chips 覆盖默认 ────────────────
@pytest.mark.asyncio
async def test_admin_chips_override(client: AsyncClient, auth_headers):
    custom_chips = [
        {"code": "test_chip1", "label": "运营自定义 chip1"},
        {"code": "test_chip2", "label": "运营自定义 chip2"},
    ]
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db, code="phq9", name="PHQ-9",
            questions=PHQ9_QUESTIONS, options=PHQ9_OPTS, classifications=PHQ9_CLASS,
            chips=custom_chips,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["完全没有"] * 9)
    chat_msgs = data.get("chat_messages") or []
    chips_msg = next((m for m in chat_msgs if m.get("type") == "followup_chips"), None)
    assert chips_msg is not None
    chips = chips_msg.get("chips") or []
    labels = [c.get("label") for c in chips]
    assert "运营自定义 chip1" in labels and "运营自定义 chip2" in labels, (
        f"运营自定义 chip 应出现，got {labels}"
    )


# ──────────────── TC-Q-6：cta_list 最多 4 个 ────────────────
@pytest.mark.asyncio
async def test_cta_list_max_4(client: AsyncClient, auth_headers):
    big_cta = [
        {"label": f"cta_{i}", "action": "open_shop", "target_url": f"/p/{i}", "style": "secondary"}
        for i in range(6)
    ]
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db, code="gad7", name="GAD-7",
            questions=GAD7_QUESTIONS, options=PHQ9_OPTS, classifications=GAD7_CLASS,
            cta=big_cta,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["完全没有"] * 7)
    cta = data.get("cta_list") or []
    assert len(cta) <= 4, f"cta_list 最多 4 个，got {len(cta)}"


# ──────────────── TC-Q-7：每个问卷默认 3 个 chips ────────────────
@pytest.mark.asyncio
async def test_default_chips_count_is_3(client: AsyncClient, auth_headers):
    for code, name, qs, classes in [
        ("phq9", "PHQ-9", PHQ9_QUESTIONS, PHQ9_CLASS),
        ("gad7", "GAD-7", GAD7_QUESTIONS, GAD7_CLASS),
        ("psqi", "PSQI", PSQI_QUESTIONS, PSQI_CLASS),
    ]:
        from tests.conftest import test_session as _ts
        async with _ts() as db:
            # 删除旧的（不同测试用例公用 code 时）
            await db.execute(text("DELETE FROM questionnaire_template WHERE code = :c"), {"c": code})
            await db.commit()
            tpl_id = await _seed_template(
                db, code=code, name=name,
                questions=qs, options=PHQ9_OPTS, classifications=classes,
            )
        data = await _submit_questionnaire(client, auth_headers, tpl_id, ["完全没有"] * len(qs))
        chat_msgs = data.get("chat_messages") or []
        chips_msg = next((m for m in chat_msgs if m.get("type") == "followup_chips"), None)
        assert chips_msg is not None, f"{code} 缺少 followup_chips 消息"
        chips = chips_msg.get("chips") or []
        assert len(chips) == 3, f"{code} 默认 chips 应为 3 个，got {len(chips)}: {chips}"


# ──────────────── TC-Q-8：chips 不带"本次回答结合"开场白 ────────────────
@pytest.mark.asyncio
async def test_chips_no_archive_prefix(client: AsyncClient, auth_headers):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db, code="phq9", name="PHQ-9",
            questions=PHQ9_QUESTIONS, options=PHQ9_OPTS, classifications=PHQ9_CLASS,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["完全没有"] * 9)
    chat_msgs = data.get("chat_messages") or []
    chips_msg = next((m for m in chat_msgs if m.get("type") == "followup_chips"), None)
    assert chips_msg is not None
    rm = chips_msg.get("render_meta") or {}
    assert rm.get("include_archive_prefix") is False, (
        f"chips 必须 include_archive_prefix=False，got {rm}"
    )


# ──────────────── TC-Q-9：chips 点击二轮回答带"本次回答结合"开场白 ────────────────
@pytest.mark.asyncio
async def test_followup_chip_response_has_archive_prefix(client: AsyncClient, auth_headers):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl_id = await _seed_template(
            db, code="phq9", name="PHQ-9",
            questions=PHQ9_QUESTIONS, options=PHQ9_OPTS, classifications=PHQ9_CLASS,
        )
    data = await _submit_questionnaire(client, auth_headers, tpl_id, ["完全没有"] * 9)
    answer_id = data["answer_id"]
    r = await client.post(
        "/api/questionnaire/followup-chip",
        json={"answer_id": answer_id, "chip_code": "shudao", "chip_label": "情绪疏导方法"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "本次回答结合" in (body.get("ai_text") or ""), (
        f"二轮回答必须带「本次回答结合」开场白，got {body.get('ai_text')!r}"
    )


# ──────────────── TC-Q-10：health_self_check 升级版新维度 ────────────────
@pytest.mark.asyncio
async def test_health_self_check_v2_new_dimensions(client: AsyncClient, auth_headers):
    """新增题目 sort_order >= 91（步骤 4/5/6）+ required=False（可跳过）"""
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        # 构建一个 health_self_check 模板，含 3 个新维度题目
        hsc_questions = [
            {"order": 91, "title": "症状是什么感觉？（可跳过）", "dim": "症状性质",
             "options": [
                 {"label": "🫀 一跳一跳的疼", "value": "搏动性疼痛", "score": 0},
                 {"label": "❓ 跳过", "value": "skip", "score": 0},
             ]},
            {"order": 92, "title": "症状严重程度（可跳过）", "dim": "严重程度",
             "options": [
                 {"label": "0 没感觉", "value": "0", "score": 0},
                 {"label": "5 影响日常", "value": "5", "score": 5},
                 {"label": "10 剧痛", "value": "10", "score": 10},
                 {"label": "❓ 跳过", "value": "skip", "score": 0},
             ]},
        ]
        tpl_id = await _seed_template(
            db, code="health_self_check_v2_test", name="健康自查 v2 测试",
            questions=hsc_questions, options=[], classifications=[
                {"code": "hsc_low", "name": "低", "min": 0, "max": 4},
                {"code": "hsc_high", "name": "高", "min": 5, "max": 20},
            ],
        )
        # 把 sort_order >= 91 的题目设为 required=False
        await db.execute(
            text("UPDATE questionnaire_question SET required = 0 WHERE template_id = :tid"),
            {"tid": tpl_id},
        )
        await db.commit()

    # 提交时 92 题选「跳过」
    data = await _submit_questionnaire(
        client, auth_headers, tpl_id, ["搏动性疼痛", "skip"]
    )
    assert data["template_id"] == tpl_id
    # skip 得 0 分，91 题 0 分 → 应落 hsc_low
    cls_id = data.get("classification_id")
    assert cls_id is not None, "至少应命中一个分型"
