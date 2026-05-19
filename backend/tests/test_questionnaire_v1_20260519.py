"""[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
通用问卷与图像采集架构重构后端测试。

测试覆盖：
1. ORM 5 张新表可正常建表
2. function_button 新字段 questionnaire_template_id / capture_purpose / pre_card_enabled 可读写
3. 管理后台 questionnaire/templates CRUD
4. 用户端答题提交 + 报告查询
5. ai_function_type=questionnaire 必填 questionnaire_template_id 校验
6. ai_function_type=image_capture 必填 capture_purpose 且取值合法
7. NEW_AI_FUNCTION_TYPES 仅 5 项（永不膨胀）
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.models import (
    QuestionnaireClassificationRule,
    QuestionnaireQuestion,
    QuestionnaireRecommendation,
    QuestionnaireTemplate,
    QuestionnaireAnswer,
)
from app.schemas.function_button import NEW_AI_FUNCTION_TYPES


@pytest.mark.asyncio
async def test_new_subtypes_are_exactly_five():
    """NEW_AI_FUNCTION_TYPES 必须恰好 5 个永久稳定子类型。"""
    assert NEW_AI_FUNCTION_TYPES == {
        "questionnaire",
        "image_capture",
        "file_upload",
        "ai_dialog_trigger",
        "quick_ask",
    }


@pytest.mark.asyncio
async def test_questionnaire_models_orm_creatable(db_session):
    """5 张新表的 ORM 实例都能正常持久化。"""
    tpl = QuestionnaireTemplate(
        code="t_demo",
        name="Demo 问卷",
        description="测试用",
        estimated_minutes=2,
        report_layout="standard",
        status=1,
    )
    db_session.add(tpl)
    await db_session.flush()

    q = QuestionnaireQuestion(
        template_id=tpl.id,
        sort_order=1,
        question_type="single_choice",
        title="您最近是否经常头痛？",
        options=[
            {"label": "经常", "value": "freq", "score": 3, "tags": []},
            {"label": "偶尔", "value": "some", "score": 1, "tags": []},
            {"label": "几乎没有", "value": "rare", "score": 0, "tags": []},
        ],
        dimension="头部",
    )
    db_session.add(q)
    await db_session.flush()

    rule = QuestionnaireClassificationRule(
        template_id=tpl.id,
        code="headache",
        name="头痛倾向",
        description="经常头痛",
        rule_type="score_range",
        rule_config={"min": 2, "max": 999},
    )
    db_session.add(rule)
    await db_session.flush()

    rec = QuestionnaireRecommendation(
        classification_id=rule.id,
        section_type="product",
        section_title="推荐头痛缓解套餐",
        match_mode="sku_list",
        sku_ids=[101, 102],
        max_items=3,
    )
    db_session.add(rec)
    await db_session.flush()

    ans = QuestionnaireAnswer(
        user_id=1,
        template_id=tpl.id,
        answers=[{"question_id": q.id, "value": "freq", "score": 3}],
        total_score=3.0,
        classification_id=rule.id,
        status="completed",
    )
    db_session.add(ans)
    await db_session.flush()
    assert tpl.id and q.id and rule.id and rec.id and ans.id


@pytest_asyncio.fixture
async def seed_template(db_session):
    """造一份完整测试模板：1 道题 + 1 个分型。"""
    tpl = QuestionnaireTemplate(
        code="health_self_check_test",
        name="健康自查（测试）",
        estimated_minutes=2,
        report_layout="standard",
        status=1,
    )
    db_session.add(tpl)
    await db_session.flush()
    q = QuestionnaireQuestion(
        template_id=tpl.id,
        sort_order=1,
        question_type="single_choice",
        title="头部是否常感不适？",
        options=[
            {"label": "是", "value": "yes", "score": 3},
            {"label": "否", "value": "no", "score": 0},
        ],
        dimension="头部",
    )
    db_session.add(q)
    rule = QuestionnaireClassificationRule(
        template_id=tpl.id,
        code="headache",
        name="头痛倾向",
        rule_type="score_range",
        rule_config={"min": 1, "max": 999},
    )
    db_session.add(rule)
    await db_session.commit()
    return {"template_id": tpl.id, "question_id": q.id, "rule_id": rule.id}


@pytest.mark.asyncio
async def test_user_submit_answer_and_get_report(
    client: AsyncClient, auth_headers, seed_template
):
    """用户提交答题 → 自动计分 + 命中分型 → 报告接口能拿到全部数据。"""
    tpl_id = seed_template["template_id"]
    q_id = seed_template["question_id"]
    rule_id = seed_template["rule_id"]

    # 1. 模板列表
    resp = await client.get("/api/questionnaire/templates")
    assert resp.status_code == 200
    items = resp.json()
    assert any(t["id"] == tpl_id for t in items)

    # 2. 模板详情
    resp = await client.get(f"/api/questionnaire/templates/{tpl_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["template"]["id"] == tpl_id
    assert len(body["questions"]) == 1
    assert len(body["classifications"]) == 1

    # 3. 按 code 查
    resp = await client.get(
        f"/api/questionnaire/templates/by-code/{seed_template and 'health_self_check_test'}"
    )
    assert resp.status_code == 200

    # 4. 提交答题
    resp = await client.post(
        "/api/questionnaire/answers",
        headers=auth_headers,
        json={
            "template_id": tpl_id,
            "answers": [{"question_id": q_id, "value": "yes"}],
        },
    )
    assert resp.status_code == 200, resp.text
    ans = resp.json()
    assert ans["total_score"] == 3.0
    assert ans["classification_id"] == rule_id
    answer_id = ans["id"]

    # 5. 报告接口
    resp = await client.get(
        f"/api/questionnaire/answers/{answer_id}/report",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["answer_id"] == answer_id
    assert report["template"]["id"] == tpl_id
    assert report["classification"]["code"] == "headache"


@pytest.mark.asyncio
async def test_admin_template_crud(client: AsyncClient, admin_headers):
    """管理后台模板 CRUD 闭环。"""
    # 创建
    resp = await client.post(
        "/api/admin/questionnaire/templates",
        headers=admin_headers,
        json={
            "code": "sleep_test_v1",
            "name": "睡眠质量测评",
            "description": "睡眠评估",
            "estimated_minutes": 5,
        },
    )
    assert resp.status_code == 200, resp.text
    tid = resp.json()["id"]

    # 同 code 再建报 400
    resp2 = await client.post(
        "/api/admin/questionnaire/templates",
        headers=admin_headers,
        json={"code": "sleep_test_v1", "name": "重复"},
    )
    assert resp2.status_code == 400

    # 列表
    resp = await client.get(
        "/api/admin/questionnaire/templates", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 更新
    resp = await client.put(
        f"/api/admin/questionnaire/templates/{tid}",
        headers=admin_headers,
        json={"name": "睡眠质量测评 v2"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "睡眠质量测评 v2"

    # 加一道题
    resp = await client.post(
        "/api/admin/questionnaire/questions",
        headers=admin_headers,
        json={
            "template_id": tid,
            "sort_order": 1,
            "question_type": "single_choice",
            "title": "您每晚平均睡几个小时？",
            "options": [
                {"label": "<5h", "value": "lt5", "score": 3},
                {"label": "6-8h", "value": "68", "score": 0},
            ],
            "dimension": "时长",
        },
    )
    assert resp.status_code == 200

    # 题目列表
    resp = await client.get(
        f"/api/admin/questionnaire/templates/{tid}/questions",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 删除模板
    resp = await client.delete(
        f"/api/admin/questionnaire/templates/{tid}", headers=admin_headers
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_function_button_questionnaire_required(
    client: AsyncClient, admin_headers
):
    """ai_function_type=questionnaire 时必须提供 questionnaire_template_id。"""
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "缺模板的问卷按钮",
            "button_type": "ai_function",
            "ai_function_type": "questionnaire",
        },
    )
    assert resp.status_code == 400
    assert "questionnaire_template_id" in resp.text


@pytest.mark.asyncio
async def test_function_button_image_capture_required(
    client: AsyncClient, admin_headers
):
    """ai_function_type=image_capture 必须 capture_purpose 且取值合法。"""
    # 没传 capture_purpose
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "缺用途的图像采集按钮",
            "button_type": "ai_function",
            "ai_function_type": "image_capture",
        },
    )
    assert resp.status_code == 400
    assert "capture_purpose" in resp.text

    # 取值非法
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "用途非法",
            "button_type": "ai_function",
            "ai_function_type": "image_capture",
            "capture_purpose": "weird",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_function_button_new_subtype_create_ok(
    client: AsyncClient, admin_headers, db_session
):
    """新主流程：创建 questionnaire / image_capture 按钮带正确字段成功。"""
    # 先建一个模板
    tpl = QuestionnaireTemplate(
        code="for_button_test",
        name="按钮测试模板",
        status=1,
    )
    db_session.add(tpl)
    await db_session.commit()

    # questionnaire 类按钮
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "健康自查",
            "icon": "🩺",
            "button_type": "ai_function",
            "ai_function_type": "questionnaire",
            "questionnaire_template_id": tpl.id,
            "pre_card_enabled": True,
            "card_title": "健康自查",
            "card_subtitle": "30 秒了解身体信号",
        },
    )
    assert resp.status_code == 200, resp.text
    btn = resp.json()
    assert btn["ai_function_type"] == "questionnaire"
    assert btn["questionnaire_template_id"] == tpl.id
    assert btn["pre_card_enabled"] is True

    # image_capture 类按钮
    resp = await client.post(
        "/api/admin/function-buttons",
        headers=admin_headers,
        json={
            "name": "识药",
            "icon": "📷",
            "button_type": "ai_function",
            "ai_function_type": "image_capture",
            "capture_purpose": "identify_medicine",
            "pre_card_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    btn2 = resp.json()
    assert btn2["ai_function_type"] == "image_capture"
    assert btn2["capture_purpose"] == "identify_medicine"
