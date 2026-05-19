"""[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
通用问卷 API：用户端 + 管理后台。

设计要点：
- 所有问卷类业务统一调用本组 API（不再为每个业务新增独立路由）
- 用户端：模板查询、答题提交、结果与报告查询
- 管理端：模板/题目/分型规则/推荐配置 CRUD
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    QuestionnaireAnswer,
    QuestionnaireClassificationRule,
    QuestionnaireQuestion,
    QuestionnaireRecommendation,
    QuestionnaireTemplate,
    User,
)
from app.schemas.questionnaire import (
    QuestionnaireAnswerResponse,
    QuestionnaireAnswerSubmit,
    QuestionnaireClassificationRuleCreate,
    QuestionnaireClassificationRuleResponse,
    QuestionnaireClassificationRuleUpdate,
    QuestionnaireQuestionCreate,
    QuestionnaireQuestionResponse,
    QuestionnaireQuestionUpdate,
    QuestionnaireRecommendationCreate,
    QuestionnaireRecommendationResponse,
    QuestionnaireRecommendationUpdate,
    QuestionnaireReportResponse,
    QuestionnaireTemplateCreate,
    QuestionnaireTemplateResponse,
    QuestionnaireTemplateUpdate,
)

router = APIRouter(prefix="/api/questionnaire", tags=["通用问卷-用户端"])
admin_router = APIRouter(
    prefix="/api/admin/questionnaire", tags=["通用问卷-管理后台"]
)

admin_dep = require_role("admin")


# ════════════════════════════════════════
#  用户端 API
# ════════════════════════════════════════


@router.get("/templates", response_model=list[QuestionnaireTemplateResponse])
async def list_active_templates(db: AsyncSession = Depends(get_db)):
    """C 端获取启用中的问卷模板列表。"""
    result = await db.execute(
        select(QuestionnaireTemplate)
        .where(QuestionnaireTemplate.status == 1)
        .order_by(QuestionnaireTemplate.id.asc())
    )
    return [
        QuestionnaireTemplateResponse.model_validate(t)
        for t in result.scalars().all()
    ]


@router.get("/templates/{template_id}")
async def get_template_detail(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    """模板详情：含模板基础信息 + 题目列表 + 分型规则。"""
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="问卷模板不存在")
    q_rows = (
        await db.execute(
            select(QuestionnaireQuestion)
            .where(QuestionnaireQuestion.template_id == template_id)
            .order_by(
                QuestionnaireQuestion.sort_order.asc(),
                QuestionnaireQuestion.id.asc(),
            )
        )
    ).scalars().all()
    rules = (
        await db.execute(
            select(QuestionnaireClassificationRule)
            .where(QuestionnaireClassificationRule.template_id == template_id)
            .order_by(QuestionnaireClassificationRule.sort_order.asc())
        )
    ).scalars().all()
    return {
        "template": QuestionnaireTemplateResponse.model_validate(tpl),
        "questions": [
            QuestionnaireQuestionResponse.model_validate(q) for q in q_rows
        ],
        "classifications": [
            QuestionnaireClassificationRuleResponse.model_validate(r) for r in rules
        ],
    }


@router.get(
    "/templates/by-code/{code}",
    response_model=QuestionnaireTemplateResponse,
)
async def get_template_by_code(code: str, db: AsyncSession = Depends(get_db)):
    """按业务编码查询模板（如 health_self_check / tcm_constitution）。"""
    row = (
        await db.execute(
            select(QuestionnaireTemplate).where(
                QuestionnaireTemplate.code == code
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"模板 {code} 不存在")
    return QuestionnaireTemplateResponse.model_validate(row)


def _compute_classification(
    template_id: int,
    rules: list[QuestionnaireClassificationRule],
    total_score: float,
    dimension_scores: dict[str, float],
) -> Optional[QuestionnaireClassificationRule]:
    """根据答题分数判定用户所属分型。

    支持三种规则：
    - score_range : rule_config = {"min": x, "max": y}
    - dimension_max : 选择 dimension_scores 中最高分对应分型（rule_config.dimension 指定）
    - tag_match : rule_config = {"tags": ["..."], "min_hits": n} — 当前最小版仅返回第一个匹配
    """
    if not rules:
        return None
    # dimension_max 模式优先：找出 score 最大的维度
    dim_rules = [r for r in rules if r.rule_type == "dimension_max"]
    if dim_rules and dimension_scores:
        best_dim = max(dimension_scores.items(), key=lambda x: x[1])[0]
        for r in dim_rules:
            cfg = r.rule_config or {}
            if cfg.get("dimension") == best_dim:
                return r
    # score_range
    for r in rules:
        if r.rule_type != "score_range":
            continue
        cfg = r.rule_config or {}
        lo = cfg.get("min", float("-inf"))
        hi = cfg.get("max", float("inf"))
        if lo <= total_score <= hi:
            return r
    # tag_match（最小版本：不计算 tags，直接落第一个）
    return rules[0]


@router.post("/answers", response_model=QuestionnaireAnswerResponse)
async def submit_answer(
    payload: QuestionnaireAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交答题：
    1. 把答案落库
    2. 按题目 options 上配置的 score / tags 计算总分与维度分
    3. 按 classification_rule 判定分型
    """
    tpl = await db.get(QuestionnaireTemplate, payload.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="问卷模板不存在")
    question_rows = (
        await db.execute(
            select(QuestionnaireQuestion).where(
                QuestionnaireQuestion.template_id == payload.template_id
            )
        )
    ).scalars().all()
    question_map = {q.id: q for q in question_rows}

    # 计分
    total_score = 0.0
    dimension_scores: dict[str, float] = {}
    answer_items: list[dict[str, Any]] = []
    for item in payload.answers:
        q = question_map.get(item.question_id)
        if not q:
            continue
        opts = q.options or []
        # 单选：value 是单个 value
        # 多选：value 是 list of value
        # 文本：value 是 str
        score = 0.0
        if q.question_type in ("single_choice", "multi_choice"):
            chosen_values = (
                [item.value] if not isinstance(item.value, list) else item.value
            )
            for opt in opts:
                if opt.get("value") in chosen_values:
                    score += float(opt.get("score", 0) or 0)
        total_score += score
        if q.dimension:
            dimension_scores[q.dimension] = (
                dimension_scores.get(q.dimension, 0.0) + score
            )
        answer_items.append(
            {
                "question_id": q.id,
                "title": q.title,
                "value": item.value,
                "score": score,
                "dimension": q.dimension,
            }
        )

    # 分型
    rules = (
        await db.execute(
            select(QuestionnaireClassificationRule).where(
                QuestionnaireClassificationRule.template_id == payload.template_id
            )
        )
    ).scalars().all()
    cls = _compute_classification(
        payload.template_id, rules, total_score, dimension_scores
    )
    classification_id = cls.id if cls else None

    ans = QuestionnaireAnswer(
        user_id=current_user.id,
        template_id=payload.template_id,
        consultant_id=payload.consultant_id,
        answers=answer_items,
        total_score=total_score,
        dimension_scores=dimension_scores or None,
        classification_id=classification_id,
        status="completed",
        completed_at=datetime.utcnow(),
    )
    db.add(ans)
    await db.flush()
    await db.refresh(ans)
    return QuestionnaireAnswerResponse.model_validate(ans)


@router.get(
    "/answers/{answer_id}",
    response_model=QuestionnaireAnswerResponse,
)
async def get_answer(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ans = await db.get(QuestionnaireAnswer, answer_id)
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答题记录不存在")
    return QuestionnaireAnswerResponse.model_validate(ans)


@router.get(
    "/answers/{answer_id}/report",
    response_model=QuestionnaireReportResponse,
)
async def get_answer_report(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """通用问卷报告页接口，返回 6 板块结构所需数据。"""
    ans = await db.get(QuestionnaireAnswer, answer_id)
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答题记录不存在")
    tpl = await db.get(QuestionnaireTemplate, ans.template_id)
    cls = None
    if ans.classification_id:
        cls = await db.get(
            QuestionnaireClassificationRule, ans.classification_id
        )
    recs_grouped: dict[str, list[dict[str, Any]]] = {}
    if cls:
        rec_rows = (
            await db.execute(
                select(QuestionnaireRecommendation)
                .where(QuestionnaireRecommendation.classification_id == cls.id)
                .order_by(QuestionnaireRecommendation.sort_order.asc())
            )
        ).scalars().all()
        for r in rec_rows:
            recs_grouped.setdefault(r.section_type, []).append(
                {
                    "id": r.id,
                    "section_title": r.section_title,
                    "match_mode": r.match_mode,
                    "sku_ids": r.sku_ids or [],
                    "tag_filters": r.tag_filters or [],
                    "max_items": r.max_items,
                }
            )

    return QuestionnaireReportResponse(
        answer_id=ans.id,
        template={
            "id": tpl.id if tpl else 0,
            "code": tpl.code if tpl else "",
            "name": tpl.name if tpl else "",
            "report_layout": tpl.report_layout if tpl else "standard",
        },
        classification=(
            {
                "id": cls.id,
                "code": cls.code,
                "name": cls.name,
                "description": cls.description,
            }
            if cls
            else None
        ),
        ai_summary=ans.ai_summary,
        dimensions=ans.dimension_scores,
        recommendations=recs_grouped,
        user_info={
            "user_id": current_user.id,
            "name": getattr(current_user, "name", "") or "",
        },
        answered_at=ans.completed_at or ans.created_at,
    )


# ════════════════════════════════════════
#  管理端 API（模板/题目/分型/推荐 CRUD）
# ════════════════════════════════════════


@admin_router.get("/templates")
async def admin_list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, or_

    stmt = select(QuestionnaireTemplate)
    count_stmt = select(func.count(QuestionnaireTemplate.id))
    if keyword:
        cond = or_(
            QuestionnaireTemplate.code.like(f"%{keyword}%"),
            QuestionnaireTemplate.name.like(f"%{keyword}%"),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        await db.execute(
            stmt.order_by(QuestionnaireTemplate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            QuestionnaireTemplateResponse.model_validate(t) for t in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.post("/templates", response_model=QuestionnaireTemplateResponse)
async def admin_create_template(
    payload: QuestionnaireTemplateCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 唯一 code 校验
    exists = (
        await db.execute(
            select(QuestionnaireTemplate).where(
                QuestionnaireTemplate.code == payload.code
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(
            status_code=400, detail=f"问卷模板编码 {payload.code} 已存在"
        )
    tpl = QuestionnaireTemplate(**payload.model_dump(exclude_unset=True))
    db.add(tpl)
    await db.flush()
    await db.refresh(tpl)
    return QuestionnaireTemplateResponse.model_validate(tpl)


@admin_router.get(
    "/templates/{template_id}",
    response_model=QuestionnaireTemplateResponse,
)
async def admin_get_template(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="问卷模板不存在")
    return QuestionnaireTemplateResponse.model_validate(tpl)


@admin_router.put(
    "/templates/{template_id}",
    response_model=QuestionnaireTemplateResponse,
)
async def admin_update_template(
    template_id: int,
    payload: QuestionnaireTemplateUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="问卷模板不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tpl, k, v)
    await db.flush()
    await db.refresh(tpl)
    return QuestionnaireTemplateResponse.model_validate(tpl)


@admin_router.delete("/templates/{template_id}")
async def admin_delete_template(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(QuestionnaireTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="问卷模板不存在")
    await db.delete(tpl)
    return {"ok": True}


# ────── Questions ──────


@admin_router.get(
    "/templates/{template_id}/questions",
    response_model=list[QuestionnaireQuestionResponse],
)
async def admin_list_questions(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(QuestionnaireQuestion)
            .where(QuestionnaireQuestion.template_id == template_id)
            .order_by(QuestionnaireQuestion.sort_order.asc())
        )
    ).scalars().all()
    return [
        QuestionnaireQuestionResponse.model_validate(q) for q in rows
    ]


@admin_router.post(
    "/questions",
    response_model=QuestionnaireQuestionResponse,
)
async def admin_create_question(
    payload: QuestionnaireQuestionCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    q = QuestionnaireQuestion(**payload.model_dump(exclude_unset=True))
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return QuestionnaireQuestionResponse.model_validate(q)


@admin_router.put(
    "/questions/{question_id}",
    response_model=QuestionnaireQuestionResponse,
)
async def admin_update_question(
    question_id: int,
    payload: QuestionnaireQuestionUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(QuestionnaireQuestion, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    await db.flush()
    await db.refresh(q)
    return QuestionnaireQuestionResponse.model_validate(q)


@admin_router.delete("/questions/{question_id}")
async def admin_delete_question(
    question_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(QuestionnaireQuestion, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    await db.delete(q)
    return {"ok": True}


# ────── Classification Rules ──────


@admin_router.get(
    "/templates/{template_id}/classifications",
    response_model=list[QuestionnaireClassificationRuleResponse],
)
async def admin_list_classifications(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(QuestionnaireClassificationRule)
            .where(
                QuestionnaireClassificationRule.template_id == template_id
            )
            .order_by(QuestionnaireClassificationRule.sort_order.asc())
        )
    ).scalars().all()
    return [
        QuestionnaireClassificationRuleResponse.model_validate(r)
        for r in rows
    ]


@admin_router.post(
    "/classifications",
    response_model=QuestionnaireClassificationRuleResponse,
)
async def admin_create_classification(
    payload: QuestionnaireClassificationRuleCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rule = QuestionnaireClassificationRule(
        **payload.model_dump(exclude_unset=True)
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return QuestionnaireClassificationRuleResponse.model_validate(rule)


@admin_router.put(
    "/classifications/{rule_id}",
    response_model=QuestionnaireClassificationRuleResponse,
)
async def admin_update_classification(
    rule_id: int,
    payload: QuestionnaireClassificationRuleUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.get(QuestionnaireClassificationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="分型规则不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await db.flush()
    await db.refresh(rule)
    return QuestionnaireClassificationRuleResponse.model_validate(rule)


@admin_router.delete("/classifications/{rule_id}")
async def admin_delete_classification(
    rule_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.get(QuestionnaireClassificationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="分型规则不存在")
    await db.delete(rule)
    return {"ok": True}


# ────── Recommendations ──────


@admin_router.get(
    "/classifications/{rule_id}/recommendations",
    response_model=list[QuestionnaireRecommendationResponse],
)
async def admin_list_recommendations(
    rule_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(QuestionnaireRecommendation)
            .where(QuestionnaireRecommendation.classification_id == rule_id)
            .order_by(QuestionnaireRecommendation.sort_order.asc())
        )
    ).scalars().all()
    return [
        QuestionnaireRecommendationResponse.model_validate(r) for r in rows
    ]


@admin_router.post(
    "/recommendations",
    response_model=QuestionnaireRecommendationResponse,
)
async def admin_create_recommendation(
    payload: QuestionnaireRecommendationCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rec = QuestionnaireRecommendation(
        **payload.model_dump(exclude_unset=True)
    )
    db.add(rec)
    await db.flush()
    await db.refresh(rec)
    return QuestionnaireRecommendationResponse.model_validate(rec)


@admin_router.put(
    "/recommendations/{rec_id}",
    response_model=QuestionnaireRecommendationResponse,
)
async def admin_update_recommendation(
    rec_id: int,
    payload: QuestionnaireRecommendationUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rec = await db.get(QuestionnaireRecommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="推荐配置不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rec, k, v)
    await db.flush()
    await db.refresh(rec)
    return QuestionnaireRecommendationResponse.model_validate(rec)


@admin_router.delete("/recommendations/{rec_id}")
async def admin_delete_recommendation(
    rec_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rec = await db.get(QuestionnaireRecommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="推荐配置不存在")
    await db.delete(rec)
    return {"ok": True}
