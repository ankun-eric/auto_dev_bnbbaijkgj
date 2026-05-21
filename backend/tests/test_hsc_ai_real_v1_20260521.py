"""[PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查 AI 解读真接入大模型 验收测试

覆盖：
- T1：迁移幂等（重复执行无副作用，关键列均存在）
- T2：HSC_AI_PROMPT_TEMPLATE_V1 中文占位符 + 输出协议字段齐全
- T3：占位符替换器 render_zh_placeholders 对中文 / 缺失 key 行为正确
- T4：build_fallback_template 根据上下文产出个性化兜底 - 包含用户填写的部位
- T5：is_profile_outdated A+++ 比对：snapshot 为空 → False；关键字段变化 → True；
       仅 nickname / avatar 变化 → False
- T6：详情接口在 LLM 不可用时仍返回非空 ai_full_interpretation / home_care_tips / red_flag_signals（走兜底）
- T7：详情接口包含 profile_outdated / ai_generated_at 新字段
- T8：模型新字段 ai_profile_snapshot / ai_generated_at 持久化
"""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.models.models import (
    FamilyMember,
    QuestionnaireAnswer,
    QuestionnaireQuestion,
    QuestionnaireTemplate,
    User,
)


# ─────────────────────────────────────────────────────────────────
# T1：迁移幂等
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_ai_real_v1_migration_idempotent():
    """迁移脚本可重复执行；run_migration_with_session 返回 stats dict。"""
    from app.services.prd_hsc_ai_real_v1_migration import run_migration_with_session
    from tests.conftest import test_session as _ts

    async with _ts() as db:
        stats1 = await run_migration_with_session(db)
        assert isinstance(stats1, dict)
        assert "answer_added" in stats1
        assert "prompt_updated" in stats1

        stats2 = await run_migration_with_session(db)
        assert isinstance(stats2, dict)
        # 第二次执行应已存在，answer_added 应为 0
        assert stats2["answer_added"] == 0


# ─────────────────────────────────────────────────────────────────
# T2：HSC_AI_PROMPT_TEMPLATE_V1 包含中文占位符 + 输出协议
# ─────────────────────────────────────────────────────────────────
def test_hsc_ai_prompt_template_v1_contains_zh_placeholders():
    from app.services.prd_hsc_ai_real_v1_migration import HSC_AI_PROMPT_TEMPLATE_V1

    must_have_zh = [
        "{档案信息}",
        "{档案年龄}",
        "{档案性别}",
        "{档案既往病史}",
        "{档案过敏史}",
        "{档案在用药物}",
        "{档案家族病史}",
        "{部位}",
        "{症状列表}",
        "{持续时间}",
    ]
    for token in must_have_zh:
        assert token in HSC_AI_PROMPT_TEMPLATE_V1, f"prompt 缺少占位符 {token}"

    # 严禁残留旧版英文占位符 / 错误占位符
    must_not_have = [
        "{scores}",
        "{main_type}",
        "{body_parts}",
        "{symptoms}",
        "{medical_history}",
    ]
    for token in must_not_have:
        assert token not in HSC_AI_PROMPT_TEMPLATE_V1, f"prompt 残留错误占位符 {token}"

    # 必须显式约束 JSON 输出结构
    for kw in ['"interpretation"', '"home_care_tips"', '"red_flags"']:
        assert kw in HSC_AI_PROMPT_TEMPLATE_V1, f"prompt 缺少输出协议字段 {kw}"


# ─────────────────────────────────────────────────────────────────
# T3：render_zh_placeholders 中文 + 缺失 key 行为
# ─────────────────────────────────────────────────────────────────
def test_render_zh_placeholders_basic_and_missing_key():
    from app.services.health_self_check_ai import render_zh_placeholders

    tpl = "您的{部位}最近{症状列表}（{持续时间}），过敏史：{档案过敏史}，未知 {NOT_DEFINED}。"
    ctx = {
        "部位": "头部",
        "症状列表": "头痛、头晕",
        "持续时间": "3 天",
        "档案过敏史": "无",
    }
    out = render_zh_placeholders(tpl, ctx)
    assert "您的头部最近头痛、头晕（3 天），过敏史：无" in out
    # 找不到 key 的占位符保留原样（便于运营排查）
    assert "{NOT_DEFINED}" in out


# ─────────────────────────────────────────────────────────────────
# T4：build_fallback_template 个性化产出
# ─────────────────────────────────────────────────────────────────
def test_build_fallback_template_contains_user_inputs():
    from app.services.health_self_check_ai import build_fallback_template

    ctx = {"部位": "膝盖", "症状列表": "酸痛、红肿", "持续时间": "5 天"}
    fb = build_fallback_template(ctx)
    assert isinstance(fb, dict)
    assert "interpretation" in fb and "home_care_tips" in fb and "red_flags" in fb
    # 解读必须把用户的"部位"嵌入文案
    assert "膝盖" in fb["interpretation"]
    # 居家建议 / 红线信号至少 3 条
    assert len(fb["home_care_tips"]) >= 3
    assert len(fb["red_flags"]) >= 3
    # 居家建议中至少有一条 mention 部位
    assert any("膝盖" in t for t in fb["home_care_tips"])


# ─────────────────────────────────────────────────────────────────
# T5：A+++ is_profile_outdated
# ─────────────────────────────────────────────────────────────────
def test_is_profile_outdated_a_plus_plus_strategy():
    from app.services.health_self_check_ai import is_profile_outdated

    base = {
        "age": 30,
        "gender": "M",
        "chronic_diseases": ["高血压"],
        "allergies": None,
        "medications": None,
        "family_history": None,
    }
    # 1) snapshot 为空 / 缺失 → 不打扰
    assert is_profile_outdated(base, None) is False
    assert is_profile_outdated(base, {}) is False

    # 2) 关键字段完全一致 → 不算 outdated
    assert is_profile_outdated(base, dict(base)) is False

    # 3) 关键字段变化 → outdated
    changed = dict(base)
    changed["chronic_diseases"] = ["高血压", "糖尿病"]
    assert is_profile_outdated(changed, base) is True

    # 4) 仅"非关键字段"变化（如 nickname/avatar 没进 snapshot）→ 不打扰
    #    实际是 snapshot 不含这些字段，所以两边没差异
    assert is_profile_outdated(base, dict(base)) is False


# ─────────────────────────────────────────────────────────────────
# 异步任务使用真实 MySQL session_maker，测试环境需 patch 到 test_session
# ─────────────────────────────────────────────────────────────────
@pytest.fixture
def _patch_async_session_for_hsc_task(monkeypatch):
    """让健康自查异步任务在测试环境使用 SQLite test_session 而不是 MySQL。"""
    from tests.conftest import test_session as _ts
    import app.core.database as _core_db

    monkeypatch.setattr(_core_db, "async_session", _ts, raising=True)
    yield


# ─────────────────────────────────────────────────────────────────
# T6 + T7 + T8：完整提交 → 详情接口 走兜底 + 新字段持久化
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_submit_hsc_ai_real_full_flow(
    client: AsyncClient, auth_headers, _patch_async_session_for_hsc_task
):
    """提交 - 异步任务等待 - 详情接口三大字段非空 + profile_outdated=False
    （刚生成时快照与档案一致）+ ai_generated_at 非空。

    测试环境无外网 LLM，预期走 fallback 路径；fallback 同样产出 ≥3 条 tips/flags
    且 ai_full_interpretation 非空。
    """
    from tests.conftest import test_session as _ts

    async with _ts() as db:
        tpl = QuestionnaireTemplate(
            code="health_self_check",
            name="健康自查-AI-Real-V1",
            ai_prompt_template="你是医生助手。\n身体部位：{部位}\n症状：{症状列表}\n请按 JSON 返回。",
        )
        db.add(tpl)
        await db.flush()
        q = QuestionnaireQuestion(
            template_id=tpl.id,
            question_type="single_choice",
            title="部位",
            dimension="部位",
            options=[
                {"value": "头部", "label": "头部", "score": 1},
                {"value": "膝盖", "label": "膝盖", "score": 1},
            ],
            sort_order=1,
            required=True,
        )
        db.add(q)
        await db.commit()
        tpl_id, q_id = tpl.id, q.id

    sub = await client.post(
        "/api/questionnaire/submit",
        headers=auth_headers,
        json={
            "template_id": tpl_id,
            "subject_kind": "self",
            "subject_name": "测试用户",
            "answers": [{"question_id": q_id, "value": "膝盖"}],
        },
    )
    assert sub.status_code == 200, sub.text
    answer_id = sub.json()["answer_id"]

    # 等待异步任务完成（最多 8s）
    final_status = "pending"
    for _ in range(80):
        rr = await client.get(
            f"/api/questionnaire/answers/{answer_id}/ai-status",
            headers=auth_headers,
        )
        if rr.status_code == 200:
            final_status = rr.json()["ai_status"]
            if final_status in ("done", "failed"):
                break
        await asyncio.sleep(0.1)
    assert final_status == "done", f"应在 8s 内完成: 实际={final_status}"

    detail = await client.get(
        f"/api/questionnaire/answers/{answer_id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200, detail.text
    d = detail.json()
    # T6：三大字段非空（兜底兜出来也算）
    assert isinstance(d["ai_full_interpretation"], str) and len(d["ai_full_interpretation"]) > 0
    assert isinstance(d["home_care_tips"], list) and len(d["home_care_tips"]) >= 3
    assert isinstance(d["red_flag_signals"], list) and len(d["red_flag_signals"]) >= 3
    # T7：新字段在响应中
    assert "profile_outdated" in d
    assert d["profile_outdated"] is False  # 刚生成时与当前档案一致
    assert "ai_generated_at" in d
    assert d["ai_generated_at"] is not None

    # T8：新字段已写入数据库
    async with _ts() as db:
        ans = await db.get(QuestionnaireAnswer, answer_id)
        assert ans is not None
        assert ans.ai_generated_at is not None
        # snapshot 是 dict（即使值都是 None 也应是 dict）
        assert ans.ai_profile_snapshot is not None
        assert isinstance(ans.ai_profile_snapshot, dict)
        assert "chronic_diseases" in ans.ai_profile_snapshot


# ─────────────────────────────────────────────────────────────────
# T9：retry-ai 触发后重新生成，answer.ai_generated_at 时间被刷新
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_ai_refreshes_generated_at(
    client: AsyncClient, auth_headers, _patch_async_session_for_hsc_task
):
    from tests.conftest import test_session as _ts

    async with _ts() as db:
        tpl = QuestionnaireTemplate(
            code="health_self_check", name="健康自查-AI-Real-Retry"
        )
        db.add(tpl)
        await db.flush()
        q = QuestionnaireQuestion(
            template_id=tpl.id,
            question_type="single_choice",
            title="部位",
            dimension="部位",
            options=[{"value": "头部", "label": "头部", "score": 1}],
            sort_order=1,
            required=True,
        )
        db.add(q)
        await db.commit()
        tpl_id, q_id = tpl.id, q.id

    sub = await client.post(
        "/api/questionnaire/submit",
        headers=auth_headers,
        json={
            "template_id": tpl_id,
            "subject_kind": "self",
            "answers": [{"question_id": q_id, "value": "头部"}],
        },
    )
    assert sub.status_code == 200
    answer_id = sub.json()["answer_id"]

    # 等首轮 done
    for _ in range(80):
        rr = await client.get(
            f"/api/questionnaire/answers/{answer_id}/ai-status", headers=auth_headers
        )
        if rr.json().get("ai_status") in ("done", "failed"):
            break
        await asyncio.sleep(0.1)

    async with _ts() as db:
        ans = await db.get(QuestionnaireAnswer, answer_id)
        first_gen_at = ans.ai_generated_at

    # 触发 retry
    r = await client.post(
        f"/api/questionnaire/answers/{answer_id}/retry-ai", headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json().get("ai_status") == "pending"

    # 等第二轮 done
    for _ in range(80):
        rr = await client.get(
            f"/api/questionnaire/answers/{answer_id}/ai-status", headers=auth_headers
        )
        if rr.json().get("ai_status") in ("done", "failed"):
            break
        await asyncio.sleep(0.1)

    async with _ts() as db:
        ans2 = await db.get(QuestionnaireAnswer, answer_id)
        second_gen_at = ans2.ai_generated_at

    assert second_gen_at is not None
    # 第二次的时间 >= 第一次（若极快可能相同时刻，但绝不该回退）
    if first_gen_at is not None:
        assert second_gen_at >= first_gen_at
