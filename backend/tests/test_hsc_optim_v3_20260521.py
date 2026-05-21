"""[PRD-HSC-OPTIM-V3-20260521] 健康自查功能优化 V3 验收测试

覆盖：
- T1-01：render-meta 返回 auto_next_enabled 并能正确开启
- T1-07：（在 autonext_v1 已覆盖，这里仅做兼容性验证）
- T2-01：提交答卷返回时 ai_status='pending'
- T2-02：异步任务完成后 ai-status 接口返回 'done'
- T2-03：详情接口包含 ai_full_interpretation / home_care_tips / red_flag_signals
- T2-04：subject_label 在家人态下返回「姓名（关系）」
- T2-06：失败重试接口 retry-ai 工作正常
- T4-01：未配置 CTA 时 详情接口的 result_cta 为 null
- T4-02：H5_PATH 类型 CTA 配置生效
- T4-05：DOCTOR_ID 类型 CTA 配置生效
- T4-06：关闭 CTA 开关后 result_cta 立即变 null
- 迁移脚本幂等
"""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.models.models import (
    ChatFunctionButton,
    FamilyMember,
    QuestionnaireAnswer,
    QuestionnaireQuestion,
    QuestionnaireTemplate,
    User,
)


async def _ensure_user_id(client: AsyncClient, auth_headers) -> int:
    r = await client.get("/api/user/profile", headers=auth_headers)
    if r.status_code == 200:
        body = r.json()
        return int(body.get("id") or body.get("user_id") or 0)
    # 兜底用 token decode
    return 0


# ─────────────────────────────────────────────────────────────────
# T1-01：render-meta 返回 auto_next_enabled
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_render_meta_auto_next_enabled(client: AsyncClient):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="hsc_v3_meta", name="meta-v3")
        db.add(tpl)
        await db.flush()
        btn = ChatFunctionButton(
            name="HSC-V3-META-BTN",
            button_type="ai_function",
            ai_function_type="questionnaire",
            questionnaire_template_id=tpl.id,
            presentation_container="DRAWER",
            questions_per_page=1,
            auto_next_enabled=True,
            is_enabled=True,
        )
        db.add(btn)
        await db.commit()
        btn_id = btn.id

    r = await client.get(f"/api/questionnaire/buttons/{btn_id}/render-meta")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auto_next_enabled"] is True
    assert body["button"]["auto_next_enabled"] is True
    # 默认未配置 result_cta → null
    assert body.get("result_cta") in (None, {})


# ─────────────────────────────────────────────────────────────────
# T4-01：未配置 CTA 时 result_cta 为 null
# T4-02：H5_PATH 类型 CTA 生效
# T4-05：DOCTOR_ID 类型 CTA 生效
# T4-06：关闭 CTA 后 立即变 null
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_result_cta_admin_config(client: AsyncClient, admin_headers):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="hsc_v3_cta", name="cta-v3")
        db.add(tpl)
        await db.flush()
        btn = ChatFunctionButton(
            name="HSC-V3-CTA-BTN",
            button_type="ai_function",
            ai_function_type="questionnaire",
            questionnaire_template_id=tpl.id,
            presentation_container="DRAWER",
            questions_per_page=1,
            auto_next_enabled=True,
            is_enabled=True,
        )
        db.add(btn)
        await db.commit()
        btn_id = btn.id

    # 默认未配置 → render-meta 返回 result_cta=null
    r0 = await client.get(f"/api/questionnaire/buttons/{btn_id}/render-meta")
    assert r0.status_code == 200
    assert r0.json().get("result_cta") in (None, {})

    # T4-02 配置 H5_PATH
    r1 = await client.put(
        f"/api/admin/function-buttons/{btn_id}",
        json={
            "result_cta_enabled": True,
            "result_cta_text": "在线问诊",
            "result_cta_target_type": "H5_PATH",
            "result_cta_target_value": "/services/consult",
        },
        headers=admin_headers,
    )
    assert r1.status_code in (200, 201), r1.text

    r2 = await client.get(f"/api/questionnaire/buttons/{btn_id}/render-meta")
    cta = r2.json().get("result_cta")
    assert cta is not None
    assert cta["text"] == "在线问诊"
    assert cta["target_type"] == "H5_PATH"
    assert cta["target_value"] == "/services/consult"

    # T4-05 改为 DOCTOR_ID
    r3 = await client.put(
        f"/api/admin/function-buttons/{btn_id}",
        json={
            "result_cta_target_type": "DOCTOR_ID",
            "result_cta_target_value": "123",
        },
        headers=admin_headers,
    )
    assert r3.status_code in (200, 201)
    cta2 = (await client.get(f"/api/questionnaire/buttons/{btn_id}/render-meta")).json().get("result_cta")
    assert cta2["target_type"] == "DOCTOR_ID"
    assert cta2["target_value"] == "123"

    # T4-06 关闭开关 → null
    r4 = await client.put(
        f"/api/admin/function-buttons/{btn_id}",
        json={"result_cta_enabled": False},
        headers=admin_headers,
    )
    assert r4.status_code in (200, 201)
    cta3 = (await client.get(f"/api/questionnaire/buttons/{btn_id}/render-meta")).json().get("result_cta")
    assert cta3 in (None, {})


# ─────────────────────────────────────────────────────────────────
# T2-01 / T2-02 / T2-03 / T2-04：提交答卷 → ai_status pending → done →
# 详情包含解读 / 居家建议 / 红线信号 + subject_label
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_submit_async_interpretation_self(
    client: AsyncClient, auth_headers
):
    from tests.conftest import test_session as _ts
    # 准备：健康自查模板 + 1 题
    async with _ts() as db:
        tpl = QuestionnaireTemplate(
            code="health_self_check",
            name="健康自查-V3-Self",
            ai_prompt_template="您好",
        )
        db.add(tpl)
        await db.flush()
        q = QuestionnaireQuestion(
            template_id=tpl.id,
            question_type="single_choice",
            title="部位",
            options=[
                {"value": "头部", "label": "头部", "score": 1},
                {"value": "胸部", "label": "胸部", "score": 1},
            ],
            sort_order=1,
            required=True,
        )
        db.add(q)
        await db.commit()
        tpl_id, q_id = tpl.id, q.id

    # 提交 - 本人
    submit = await client.post(
        "/api/questionnaire/submit",
        headers=auth_headers,
        json={
            "template_id": tpl_id,
            "consultant_id": None,
            "subject_kind": "self",
            "subject_name": "测试用户",
            "answers": [{"question_id": q_id, "value": "头部"}],
        },
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    answer_id = body["answer_id"]
    assert answer_id

    # T2-01：提交后 ai-status 应为 pending（瞬时）或 done（异步极快）
    st0 = await client.get(
        f"/api/questionnaire/answers/{answer_id}/ai-status",
        headers=auth_headers,
    )
    assert st0.status_code == 200
    s0 = st0.json()["ai_status"]
    assert s0 in ("pending", "done")

    # T2-02：等待最多 6 秒让异步任务完成
    final_status = s0
    for _ in range(60):
        if final_status == "done":
            break
        await asyncio.sleep(0.1)
        rr = await client.get(
            f"/api/questionnaire/answers/{answer_id}/ai-status",
            headers=auth_headers,
        )
        if rr.status_code == 200:
            final_status = rr.json()["ai_status"]
    assert final_status == "done", f"ai_status 应在 6s 内变 done, 实际={final_status}"

    # T2-03：详情接口字段齐全
    detail = await client.get(
        f"/api/questionnaire/answers/{answer_id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200, detail.text
    d = detail.json()
    assert d["ai_status"] == "done"
    assert isinstance(d["ai_full_interpretation"], str) and len(d["ai_full_interpretation"]) > 0
    assert isinstance(d["home_care_tips"], list) and len(d["home_care_tips"]) > 0
    assert isinstance(d["red_flag_signals"], list) and len(d["red_flag_signals"]) > 0
    # T2-04（本人态）：subject_label='本人'
    assert d["subject_label"] == "本人"
    # 未配置 CTA → null
    assert d.get("result_cta") in (None, {})


# ─────────────────────────────────────────────────────────────────
# T2-04：family 模式 subject_label = 「姓名（关系）」
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_submit_family_subject_label(
    client: AsyncClient, auth_headers
):
    from tests.conftest import test_session as _ts
    # 找到当前测试用户 id
    async with _ts() as db:
        u_row = await db.execute(
            __import__("sqlalchemy").select(User).where(User.phone == "13900000001")
        )
        user = u_row.scalar_one()
        # 建一个家人
        fm = FamilyMember(
            user_id=user.id,
            nickname="张红",
            relationship_type="母亲",
            is_self=False,
        )
        db.add(fm)

        tpl = QuestionnaireTemplate(
            code="health_self_check",
            name="健康自查-V3-Family",
        )
        db.add(tpl)
        await db.flush()
        q = QuestionnaireQuestion(
            template_id=tpl.id,
            question_type="single_choice",
            title="部位",
            options=[{"value": "头部", "label": "头部", "score": 1}],
            sort_order=1,
            required=True,
        )
        db.add(q)
        await db.commit()
        tpl_id, q_id, fm_id = tpl.id, q.id, fm.id

    submit = await client.post(
        "/api/questionnaire/submit",
        headers=auth_headers,
        json={
            "template_id": tpl_id,
            "consultant_id": fm_id,
            "subject_kind": "family",
            "subject_member_id": fm_id,
            "subject_name": "张红",
            "subject_relation": "母亲",
            "answers": [{"question_id": q_id, "value": "头部"}],
        },
    )
    assert submit.status_code == 200, submit.text
    answer_id = submit.json()["answer_id"]

    detail = await client.get(
        f"/api/questionnaire/answers/{answer_id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    d = detail.json()
    assert d["subject_kind"] == "family"
    assert d["subject_name"] == "张红"
    assert d["subject_relation"] == "母亲"
    assert d["subject_label"] == "张红（母亲）"


# ─────────────────────────────────────────────────────────────────
# T2-06：retry-ai 接口工作正常
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_retry_ai(client: AsyncClient, auth_headers):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(
            code="health_self_check", name="健康自查-V3-Retry"
        )
        db.add(tpl)
        await db.flush()
        q = QuestionnaireQuestion(
            template_id=tpl.id,
            question_type="single_choice",
            title="部位",
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

    # 显式 retry，立即应返回 pending
    r = await client.post(
        f"/api/questionnaire/answers/{answer_id}/retry-ai",
        headers=auth_headers,
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ai_status"] == "pending"


# ─────────────────────────────────────────────────────────────────
# 迁移脚本幂等性
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_migration_idempotent():
    from app.core.database import async_session
    from app.services.prd_hsc_optim_v3_migration import run_migration_with_session

    async with async_session() as db1:
        s1 = await run_migration_with_session(db1)
    async with async_session() as db2:
        s2 = await run_migration_with_session(db2)
    assert isinstance(s1, dict)
    assert isinstance(s2, dict)
    # 第二次必定 0
    assert s2.get("answer_added", 0) == 0
    assert s2.get("button_added", 0) == 0


# ─────────────────────────────────────────────────────────────────
# 详情接口透传 result_cta：通过模板的 questionnaire 按钮反查
# ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hsc_v3_detail_result_cta_inheritance(
    client: AsyncClient, auth_headers, admin_headers
):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(
            code="health_self_check", name="健康自查-V3-CTA-Detail"
        )
        db.add(tpl)
        await db.flush()
        q = QuestionnaireQuestion(
            template_id=tpl.id,
            question_type="single_choice",
            title="部位",
            options=[{"value": "头部", "label": "头部", "score": 1}],
            sort_order=1,
            required=True,
        )
        db.add(q)
        btn = ChatFunctionButton(
            name="HSC-V3-CTA-Detail-BTN",
            button_type="ai_function",
            ai_function_type="questionnaire",
            questionnaire_template_id=tpl.id,
            presentation_container="DRAWER",
            questions_per_page=1,
            auto_next_enabled=True,
            is_enabled=True,
            result_cta_enabled=True,
            result_cta_text="找医生咨询",
            result_cta_target_type="DOCTOR_ID",
            result_cta_target_value="42",
        )
        db.add(btn)
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
    assert sub.status_code == 200, sub.text
    answer_id = sub.json()["answer_id"]

    detail = await client.get(
        f"/api/questionnaire/answers/{answer_id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200, detail.text
    d = detail.json()
    cta = d.get("result_cta")
    assert cta is not None
    assert cta["target_type"] == "DOCTOR_ID"
    assert cta["target_value"] == "42"
    assert cta["text"] == "找医生咨询"
