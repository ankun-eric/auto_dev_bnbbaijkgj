"""[PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用卡片消息协议 · 验收测试

覆盖三大 Bug 修复 + 通用协议：

- TC-BUG1：chat_messages 序列顺序为 card → text → followup_chips
- TC-BUG2-1：所有 chat_messages 的 sender 必须为 'ai'，禁止 user 身份
- TC-BUG2-2：所有 chat_messages 内容字符串中不出现 {main_type}/{secondary_types}/{scores}
                  等业务级未渲染占位符
- TC-BUG3：questionnaire_result_card 包含 main_type / scores / detail_target 等字段
- TC-FW-CHIPS：chips 默认带 3 个；render_meta.include_archive_prefix == False
- TC-FW-CHIP-API：/api/questionnaire/followup-chip 返回的 ai_text 必须带"本次回答结合"开场白
- TC-FW-TCM-CONSTITUTION-TEST：/api/tcm/constitution-test 也返回 chat_messages 序列
- TC-FW-MULTI：不同问卷类型 chips 列表不同
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.models.models import QuestionnaireAnswer, QuestionnaireTemplate, ConstitutionQuestion
from app.services.prd_tcm36_drawer_v12_migration import _seed_tcm36_template_and_questions


FORBIDDEN_PLACEHOLDERS = ["{main_type}", "{secondary_types}", "{scores}"]


def _assert_no_placeholders(s: str, label: str = ""):
    assert isinstance(s, str), f"{label} should be str, got {type(s)}"
    for ph in FORBIDDEN_PLACEHOLDERS:
        assert ph not in s, f"{label} contains forbidden placeholder {ph}: {s!r}"


async def _submit_tcm_questionnaire(client: AsyncClient, auth_headers):
    """seed 36 题模板 + 提交答卷，返回 response.json()"""
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        stats = await _seed_tcm36_template_and_questions(db)
        await db.commit()
        tpl_id = stats["template_id"]
        rows = (
            await db.execute(
                text(
                    "SELECT id, sort_order, dimension FROM questionnaire_question "
                    "WHERE template_id = :tid ORDER BY sort_order ASC"
                ),
                {"tid": tpl_id},
            )
        ).fetchall()
    answers = []
    for row in rows:
        qid, _order, dim = row[0], row[1], row[2]
        # 痰湿质全选"总是"以触发"主体质=痰湿质"，正好对应 Bug 截图场景
        val = "总是" if dim == "痰湿质" else "没有"
        answers.append({"question_id": qid, "value": val})
    r = await client.post(
        "/api/questionnaire/submit",
        json={"template_id": tpl_id, "answers": answers},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────── TC-BUG1：消息顺序 ────────────────
@pytest.mark.asyncio
async def test_bug1_chat_messages_order(client: AsyncClient, auth_headers):
    """chat_messages 必须按 card → text → followup_chips 顺序"""
    data = await _submit_tcm_questionnaire(client, auth_headers)
    chat_msgs = data.get("chat_messages")
    assert isinstance(chat_msgs, list) and len(chat_msgs) >= 3, (
        f"chat_messages must have >=3 items, got {chat_msgs!r}"
    )
    types = [m.get("type") for m in chat_msgs]
    assert types[0] == "questionnaire_result_card", f"first must be card, got {types}"
    assert types[1] == "text", f"second must be text, got {types}"
    assert types[2] == "followup_chips", f"last must be chips, got {types}"


# ──────────────── TC-BUG2-1：所有消息 sender=ai ────────────────
@pytest.mark.asyncio
async def test_bug2_all_messages_sender_ai(client: AsyncClient, auth_headers):
    """严禁 user 身份的"总结"消息"""
    data = await _submit_tcm_questionnaire(client, auth_headers)
    chat_msgs = data.get("chat_messages") or []
    for m in chat_msgs:
        assert m.get("sender") == "ai", f"non-ai sender found: {m}"


# ──────────────── TC-BUG2-2：占位符已完全渲染 ────────────────
@pytest.mark.asyncio
async def test_bug2_no_unrendered_placeholders(client: AsyncClient, auth_headers):
    """{main_type}/{secondary_types}/{scores} 必须在后端渲染完毕，
    不允许出现在 chat_messages、summary_text、active_followup、result_card_payload 中。
    """
    data = await _submit_tcm_questionnaire(client, auth_headers)
    # active_followup
    af = data.get("active_followup")
    if af:
        _assert_no_placeholders(af, "active_followup")
    # card.summary_text
    summary = (data.get("card") or {}).get("summary_text")
    if summary:
        _assert_no_placeholders(summary, "card.summary_text")
    # chat_messages 中所有 text
    chat_msgs = data.get("chat_messages") or []
    for m in chat_msgs:
        if m.get("type") == "text":
            _assert_no_placeholders(m.get("text") or "", "chat_messages.text")
        if m.get("type") == "questionnaire_result_card":
            card = m.get("card") or {}
            for k in ("summary_text", "main_type_desc"):
                v = card.get(k)
                if isinstance(v, str):
                    _assert_no_placeholders(v, f"card.{k}")
    # result_card_payload
    rcp = data.get("result_card_payload") or {}
    for k in ("summary_text", "main_type_desc"):
        v = rcp.get(k)
        if isinstance(v, str):
            _assert_no_placeholders(v, f"result_card_payload.{k}")


# ──────────────── TC-BUG3：结果汇总卡片字段完整 ────────────────
@pytest.mark.asyncio
async def test_bug3_card_has_main_type_scores_detail(client: AsyncClient, auth_headers):
    """questionnaire_result_card.card 必须包含 main_type / scores / detail_target / cover_style"""
    data = await _submit_tcm_questionnaire(client, auth_headers)
    chat_msgs = data.get("chat_messages") or []
    card_msg = next((m for m in chat_msgs if m.get("type") == "questionnaire_result_card"), None)
    assert card_msg is not None, "no questionnaire_result_card found"
    card = card_msg.get("card") or {}
    assert card.get("main_type"), f"main_type missing: {card!r}"
    # 痰湿质主体质
    assert card.get("main_type") == "痰湿质", f"expected 痰湿质, got {card.get('main_type')!r}"
    assert isinstance(card.get("scores"), dict) and len(card["scores"]) >= 9, (
        f"scores incomplete: {card.get('scores')!r}"
    )
    assert card.get("detail_target"), f"detail_target missing: {card!r}"
    assert card.get("cover_style") == "universal_v1", (
        f"cover_style should be universal_v1, got {card.get('cover_style')!r}"
    )
    # 描述、副体质
    assert "main_type_desc" in card
    assert isinstance(card.get("secondary_types"), list)


# ──────────────── TC-FW-CHIPS：chips 默认 3 个 + 不带开场白 ────────────────
@pytest.mark.asyncio
async def test_fw_chips_default_three_no_prefix(client: AsyncClient, auth_headers):
    data = await _submit_tcm_questionnaire(client, auth_headers)
    chat_msgs = data.get("chat_messages") or []
    chips_msg = next((m for m in chat_msgs if m.get("type") == "followup_chips"), None)
    assert chips_msg is not None, "no followup_chips found"
    chips = chips_msg.get("chips") or []
    assert len(chips) == 3, f"chips should be 3, got {len(chips)}: {chips!r}"
    # 默认三大 chip
    labels = [c.get("label") for c in chips]
    assert "调理方法" in labels
    assert "饮食禁忌" in labels
    assert "适合运动" in labels
    # 关键：chips 不带"本次回答结合"开场白
    rm = chips_msg.get("render_meta") or {}
    assert rm.get("include_archive_prefix") is False, (
        f"chips include_archive_prefix should be False, got {rm!r}"
    )


# ──────────────── TC-FW-TEXT：AI 解读首条带"本次回答结合"开场白 ────────────────
@pytest.mark.asyncio
async def test_fw_text_first_has_archive_prefix(client: AsyncClient, auth_headers):
    data = await _submit_tcm_questionnaire(client, auth_headers)
    chat_msgs = data.get("chat_messages") or []
    text_msg = next((m for m in chat_msgs if m.get("type") == "text"), None)
    assert text_msg is not None, "no text msg found"
    body = text_msg.get("text") or ""
    assert "本次回答结合" in body, f"text msg must include archive prefix: {body!r}"
    rm = text_msg.get("render_meta") or {}
    assert rm.get("include_archive_prefix") is True


# ──────────────── TC-FW-CHIP-API：chip 追问接口 ────────────────
@pytest.mark.asyncio
async def test_fw_followup_chip_api(client: AsyncClient, auth_headers):
    """POST /api/questionnaire/followup-chip 返回的 ai_text 必须带开场白"""
    data = await _submit_tcm_questionnaire(client, auth_headers)
    answer_id = data["answer_id"]
    r = await client.post(
        "/api/questionnaire/followup-chip",
        json={
            "answer_id": answer_id,
            "chip_code": "tiaoli_method",
            "chip_label": "调理方法",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    ai_text = body.get("ai_text") or ""
    assert "本次回答结合" in ai_text, (
        f"chip reply must include '本次回答结合' prefix: {ai_text!r}"
    )
    assert body.get("include_archive_prefix") is True
    # 不能有占位符
    _assert_no_placeholders(ai_text, "followup-chip.ai_text")


# ──────────────── TC-FW-MULTI：health_self_check 卷的 chips 与体质卷不同 ────────────────
@pytest.mark.asyncio
async def test_fw_chips_per_questionnaire(client: AsyncClient, auth_headers):
    """不同问卷类型应有不同的默认 chips（验证通用框架）"""
    from app.api.questionnaire import _build_followup_chips
    chips_tcm = _build_followup_chips("tcm_constitution")
    chips_hsc = _build_followup_chips("health_self_check")
    chips_phq9 = _build_followup_chips("phq9")
    chips_gad7 = _build_followup_chips("gad7")
    chips_psqi = _build_followup_chips("psqi")
    assert chips_tcm != chips_hsc
    assert chips_tcm != chips_phq9
    assert chips_hsc != chips_phq9
    # 都至少 3 个
    for c in [chips_tcm, chips_hsc, chips_phq9, chips_gad7, chips_psqi]:
        assert len(c) >= 3
        for item in c:
            assert "code" in item and "label" in item


# ──────────────── TC-FW-TCM-CONSTITUTION-TEST ────────────────
@pytest.mark.asyncio
async def test_fw_tcm_constitution_test_also_returns_chat_messages(client: AsyncClient, auth_headers):
    """旧版 /api/tcm/constitution-test 也按协议返回 chat_messages"""
    from tests.conftest import test_session as _ts
    # seed 旧版 8 题（旧表 constitution_questions）
    async with _ts() as db:
        for i in range(1, 9):
            db.add(ConstitutionQuestion(
                id=i,
                order_num=i,
                question_text=f"题 {i}",
                question_group="阳虚质",
                is_reverse_score=False,
            ))
        await db.commit()
    answers = []
    for i in range(1, 9):
        answers.append({"question_id": i, "answer_value": "总是", "option_index": 4})
    r = await client.post(
        "/api/tcm/constitution-test",
        json={"answers": answers},
        headers=auth_headers,
    )
    # 可能因 AI 模型未配置返回 200（兜底）或非 200，我们容忍 AI 兜底
    assert r.status_code == 200, r.text
    d = r.json()
    # 必须包含 chat_messages 字段
    assert "chat_messages" in d, f"chat_messages missing in {d!r}"
    chat_msgs = d.get("chat_messages") or []
    if chat_msgs:
        # 顺序也必须正确
        types = [m.get("type") for m in chat_msgs]
        assert types[0] == "questionnaire_result_card"
        assert types[-1] == "followup_chips"
        # 全部 sender=ai
        for m in chat_msgs:
            assert m.get("sender") == "ai"
        # 无占位符
        for m in chat_msgs:
            if m.get("type") == "text":
                _assert_no_placeholders(m.get("text") or "", "tcm_constitution_test.text")


# ──────────────── TC-FW-IDEMPOTENT：多次构造 helper 应稳定 ────────────────
@pytest.mark.asyncio
async def test_fw_business_placeholder_renderer():
    """_render_business_placeholders 把 {main_type} 等占位符替换为真实值"""
    from app.api.questionnaire import _render_business_placeholders
    r1 = _render_business_placeholders(
        "主：{main_type}，兼：{secondary_types}，分：{scores}",
        main_type="痰湿质",
        secondary_types=["气虚质", "湿热质"],
        scores={"痰湿质": 72.0, "气虚质": 45.0},
    )
    for ph in FORBIDDEN_PLACEHOLDERS:
        assert ph not in r1, f"{ph} not rendered: {r1!r}"
    assert "痰湿质" in r1
    assert "气虚质、湿热质" in r1
    # 空主体质场景
    r2 = _render_business_placeholders(
        "{main_type} 兼 {secondary_types}",
        main_type=None,
        secondary_types=None,
        scores=None,
    )
    for ph in FORBIDDEN_PLACEHOLDERS:
        assert ph not in r2
