"""[PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 自动下一步呈现配置三件套验收测试

覆盖：
- TC-01：ChatFunctionButton 新增 3 字段 ORM 可读写
- TC-02：admin API 创建按钮带新字段往返一致
- TC-03：admin API 联动校验 —— 容器=INLINE_CHAT 时不能开启 auto_next_enabled
- TC-04：admin API 联动校验 —— questions_per_page > 1 时不能开启 auto_next_enabled
- TC-05：admin API 字段校验 —— questions_per_page 必须 1~999
- TC-06：questionnaire/buttons/{id}/render-meta 接口返回新字段
- TC-07：迁移脚本可幂等重跑
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.models import ChatFunctionButton, QuestionnaireTemplate


# ──────────────── TC-01：ORM 新字段读写 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc01_orm_fields(db_session):
    btn = ChatFunctionButton(
        name="自动下一步测试按钮",
        button_type="ai_function",
        ai_function_type="questionnaire",
        presentation_container="DRAWER",
        questions_per_page=1,
        auto_next_enabled=True,
    )
    db_session.add(btn)
    await db_session.flush()
    assert btn.presentation_container == "DRAWER"
    assert btn.questions_per_page == 1
    assert btn.auto_next_enabled is True


# ──────────────── TC-02：admin API 创建+读回 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc02_admin_roundtrip(client: AsyncClient, admin_headers):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="t_autonext_rt", name="自动跳题往返")
        db.add(tpl)
        await db.commit()
        tpl_id = tpl.id

    payload = {
        "name": "AN-RT-按钮",
        "button_type": "ai_function",
        "ai_function_type": "questionnaire",
        "questionnaire_template_id": tpl_id,
        "questionnaire_display_form": "DRAWER_STEPPED",
        "presentation_container": "DRAWER",
        "questions_per_page": 1,
        "auto_next_enabled": True,
        "pre_card_enabled": True,
    }
    r = await client.post(
        "/api/admin/function-buttons", json=payload, headers=admin_headers
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["presentation_container"] == "DRAWER"
    assert body["questions_per_page"] == 1
    assert body["auto_next_enabled"] is True


# ──────────────── TC-03：容器=INLINE_CHAT 时不能开自动下一步 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc03_inline_chat_cant_autonext(
    client: AsyncClient, admin_headers
):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="t_autonext_inline", name="内联")
        db.add(tpl)
        await db.commit()
        tpl_id = tpl.id

    payload = {
        "name": "AN-INLINE-按钮",
        "button_type": "ai_function",
        "ai_function_type": "questionnaire",
        "questionnaire_template_id": tpl_id,
        "questionnaire_display_form": "INLINE_CHAT",
        "presentation_container": "INLINE_CHAT",
        "questions_per_page": 1,
        "auto_next_enabled": True,  # 非法
    }
    r = await client.post(
        "/api/admin/function-buttons", json=payload, headers=admin_headers
    )
    assert r.status_code == 400, r.text
    assert "对话内插入" in r.text or "INLINE_CHAT" in r.text


# ──────────────── TC-04：每页题数>1 时不能开自动下一步 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc04_qpp_gt1_cant_autonext(
    client: AsyncClient, admin_headers
):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="t_autonext_qpp", name="多题")
        db.add(tpl)
        await db.commit()
        tpl_id = tpl.id

    payload = {
        "name": "AN-QPP-按钮",
        "button_type": "ai_function",
        "ai_function_type": "questionnaire",
        "questionnaire_template_id": tpl_id,
        "questionnaire_display_form": "DRAWER_SCROLL",
        "presentation_container": "DRAWER",
        "questions_per_page": 10,
        "auto_next_enabled": True,  # 非法
    }
    r = await client.post(
        "/api/admin/function-buttons", json=payload, headers=admin_headers
    )
    assert r.status_code == 400, r.text
    assert "每页题数" in r.text or "questions_per_page" in r.text


# ──────────────── TC-05：questions_per_page 范围校验 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc05_qpp_out_of_range(
    client: AsyncClient, admin_headers
):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="t_autonext_range", name="范围")
        db.add(tpl)
        await db.commit()
        tpl_id = tpl.id

    # 0 / 负数 / 1001 都应被拒绝
    for bad in (0, -1, 1001):
        payload = {
            "name": f"AN-RANGE-{bad}",
            "button_type": "ai_function",
            "ai_function_type": "questionnaire",
            "questionnaire_template_id": tpl_id,
            "questionnaire_display_form": "DRAWER_SCROLL",
            "presentation_container": "DRAWER",
            "questions_per_page": bad,
            "auto_next_enabled": False,
        }
        r = await client.post(
            "/api/admin/function-buttons", json=payload, headers=admin_headers
        )
        assert r.status_code == 400, (
            f"qpp={bad} should be rejected but got {r.status_code}: {r.text}"
        )


# ──────────────── TC-06：render-meta 返回新字段 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc06_render_meta_returns_new_fields(
    client: AsyncClient, admin_headers
):
    from tests.conftest import test_session as _ts
    async with _ts() as db:
        tpl = QuestionnaireTemplate(code="t_autonext_meta", name="meta")
        db.add(tpl)
        await db.flush()
        btn = ChatFunctionButton(
            name="AN-META-按钮",
            button_type="ai_function",
            ai_function_type="questionnaire",
            questionnaire_template_id=tpl.id,
            questionnaire_display_form="DRAWER_STEPPED",
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
    assert body.get("presentation_container") == "DRAWER"
    assert body.get("questions_per_page") == 1
    assert body.get("auto_next_enabled") is True
    btn_meta = body.get("button") or {}
    assert btn_meta.get("auto_next_enabled") is True
    assert btn_meta.get("questions_per_page") == 1


# ──────────────── TC-07：迁移幂等性 ────────────────
@pytest.mark.asyncio
async def test_autonext_tc07_migration_idempotent():
    """连续跑两次迁移不应抛异常，第二次列已存在应跳过。"""
    from app.services.prd_questionnaire_autonext_v1_migration import (
        run_migration_with_session,
    )
    from app.core.database import async_session

    stats1 = await run_migration_with_session(async_session)
    stats2 = await run_migration_with_session(async_session)
    assert isinstance(stats1, dict)
    assert isinstance(stats2, dict)
    # 第二次不应再添加列（columns_added 必然为 0 或保持原值）
    assert stats2["columns_added"] == 0
