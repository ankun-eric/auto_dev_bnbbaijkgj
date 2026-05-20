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
    ChatFunctionButton,
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


# [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 按钮渲染元信息接口
@router.get("/buttons/{button_id}/render-meta")
async def get_button_render_meta(
    button_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取一个 AI 功能按钮的渲染元信息。

    若按钮 ai_function_type=questionnaire，返回：
    - display_form：DRAWER_SCROLL / DRAWER_STEPPED / INLINE_CHAT
    - template：模板元信息（含 result_summary_template / source）
    - questions：题目列表（含 display_condition_json / option_filter_json / layout_hint）
    """
    btn = await db.get(ChatFunctionButton, button_id)
    if not btn:
        raise HTTPException(status_code=404, detail="按钮不存在")
    meta: dict[str, Any] = {
        "button": {
            "id": btn.id,
            "name": btn.name,
            "button_type": btn.button_type,
            "ai_function_type": btn.ai_function_type,
            "questionnaire_template_id": btn.questionnaire_template_id,
            "questionnaire_display_form": btn.questionnaire_display_form or "DRAWER_SCROLL",
            "ai_opening": btn.ai_opening,
            "prompt_override_enabled": btn.prompt_override_enabled,
            "prompt_override_text": btn.prompt_override_text,
            "card_title": btn.card_title,
            "card_subtitle": btn.card_subtitle,
            "card_cover_image": btn.card_cover_image,
            "button_sub_desc": btn.button_sub_desc,
            # [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片三字段
            "pre_card_enabled": bool(btn.pre_card_enabled) if btn.pre_card_enabled is not None else True,
            "pre_card_icon": btn.pre_card_icon,
            "pre_card_icon_type": btn.pre_card_icon_type or "default",
        },
        "display_form": btn.questionnaire_display_form or "DRAWER_SCROLL",
        "template": None,
        "questions": [],
    }
    tpl_id = btn.questionnaire_template_id
    if not tpl_id and btn.ai_function_type == "questionnaire":
        return meta
    if tpl_id:
        tpl = await db.get(QuestionnaireTemplate, tpl_id)
        if tpl:
            meta["template"] = {
                "id": tpl.id,
                "code": tpl.code,
                "name": tpl.name,
                "description": tpl.description,
                "intro_text": tpl.intro_text,
                "estimated_minutes": tpl.estimated_minutes,
                "allow_back": tpl.allow_back,
                "result_summary_template": tpl.result_summary_template,
                "source": tpl.source,
                "ai_prompt_template": tpl.ai_prompt_template,
                "ai_opening": tpl.ai_opening,
                "report_layout": tpl.report_layout,
            }
            q_rows = (
                await db.execute(
                    select(QuestionnaireQuestion)
                    .where(QuestionnaireQuestion.template_id == tpl_id)
                    .order_by(
                        QuestionnaireQuestion.sort_order.asc(),
                        QuestionnaireQuestion.id.asc(),
                    )
                )
            ).scalars().all()
            meta["questions"] = [
                {
                    "id": q.id,
                    "sort_order": q.sort_order,
                    "question_type": q.question_type,
                    "title": q.title,
                    "subtitle": q.subtitle,
                    "required": q.required,
                    "options": q.options or [],
                    "dimension": q.dimension,
                    "display_condition_json": q.display_condition_json,
                    "option_filter_json": q.option_filter_json,
                    "layout_hint": q.layout_hint or "tag_grid",
                }
                for q in q_rows
            ]
    return meta


def _render_result_summary(
    template: Optional[str],
    answer_items: list[dict[str, Any]],
) -> Optional[str]:
    """把 result_summary_template 里的 {题目名/dimension} 占位符替换为答案文案。

    优先级：dimension → title 末段 → 跳过。
    多选答案用 `、` 拼接；单选直接显示 value；文本题直接显示文本。
    """
    if not template:
        return None
    out = template
    for ai in answer_items:
        val = ai.get("value")
        text_val: str
        if isinstance(val, list):
            text_val = "、".join(str(v) for v in val if v is not None and str(v) != "")
        elif val is None:
            text_val = ""
        else:
            text_val = str(val)
        keys = []
        dim = ai.get("dimension")
        if dim:
            keys.append(dim)
        title = ai.get("title") or ""
        if title:
            keys.append(title)
        for k in keys:
            placeholder = "{" + k + "}"
            if placeholder in out:
                out = out.replace(placeholder, text_val)
    return out


# [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 抽屉提交接口
@router.post("/submit")
async def submit_questionnaire(
    payload: QuestionnaireAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """抽屉提交接口：与 POST /answers 行为一致，但额外返回"问卷结果卡片"渲染所需结构。

    返回结构：
    {
      "answer_id": int,
      "card": {
        "template_name": str,
        "summary_text": str | None,
        "fields": [{"key", "label", "value"}],
        "template_code": str,
        "icon": "🩺"
      },
      "ai_prompt_hint": str | None
    }
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

    total_score = 0.0
    dimension_scores: dict[str, float] = {}
    answer_items: list[dict[str, Any]] = []
    for item in payload.answers:
        q = question_map.get(item.question_id)
        if not q:
            continue
        opts = q.options or []
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
                "dimension": q.dimension,
                "value": item.value,
                "score": score,
            }
        )

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

    # 构建结果卡片
    summary_text = _render_result_summary(tpl.result_summary_template, answer_items)
    fields: list[dict[str, Any]] = []
    for ai in answer_items:
        val = ai.get("value")
        if isinstance(val, list):
            display = "、".join(str(v) for v in val if v is not None and str(v) != "")
        elif val is None:
            display = ""
        else:
            display = str(val)
        label = ai.get("dimension") or ai.get("title") or ""
        fields.append(
            {
                "key": ai.get("dimension") or f"q_{ai.get('question_id')}",
                "label": label,
                "value": display,
            }
        )

    icon_map = {
        "health_self_check": "🩺",
        "tcm_constitution": "🌿",
    }
    icon = icon_map.get(tpl.code or "", "📝")

    # [PRD-TCM-DRAWER-V12 2026-05-20] 中医体质：主动追问消息
    active_followup: Optional[str] = None
    if tpl.code == "tcm_constitution":
        try:
            from app.services.constitution_score import calculate_constitution
            # 把 answer_items 改造成 constitution_score 期望的输入
            cs_items: list[dict[str, Any]] = []
            for ai in answer_items:
                # 找到对应 question 的 dimension（即 group）和 sort_order（即 order_num）
                q = question_map.get(ai.get("question_id"))
                if not q:
                    continue
                # 反向题：display_condition_json 里存了 is_reverse_score
                meta = q.display_condition_json or {}
                cs_items.append({
                    "group": q.dimension,
                    "order_num": meta.get("order_num") or q.sort_order,
                    "is_reverse_score": bool(meta.get("is_reverse_score")),
                    "answer_value": ai.get("value"),
                })
            res = calculate_constitution(cs_items)
            main_type = res.main_type
            # 用 main_type 覆盖默认 classification（如果尚未命中）
            if not classification_id:
                cls_row = (
                    await db.execute(
                        select(QuestionnaireClassificationRule).where(
                            QuestionnaireClassificationRule.template_id == tpl.id,
                            QuestionnaireClassificationRule.name == main_type,
                        )
                    )
                ).scalar_one_or_none()
                if cls_row:
                    ans.classification_id = cls_row.id
                    classification_id = cls_row.id
            # 把 9 项转换分写回 dimension_scores
            ans.dimension_scores = res.scores
            # 写回 answers 中的 group/order_num（便于后续回溯）
            active_followup = f"您的体质属于「{main_type}」，需要我详细介绍「{main_type}」的具体调理方法吗？"
            await db.flush()
        except Exception as e:  # noqa: BLE001
            import logging as _l
            _l.getLogger(__name__).warning("tcm constitution active followup failed: %s", e)

    # [PRD-TAG-RECOMMEND-V1 2026-05-20] 三段式：返回推荐商品 + 配置开关
    recommend_goods: list[dict[str, Any]] = []
    result_display_mode = tpl.result_display_mode or "simple"
    recommend_click_mode = tpl.recommend_click_mode or "drawer"
    recommend_display_count = tpl.recommend_display_count or 6
    ai_followup_enabled = bool(tpl.ai_followup_enabled) if tpl.ai_followup_enabled is not None else True
    try:
        # 获取分型 code 供推荐计算
        cls_code: Optional[str] = None
        if ans.classification_id:
            crow = await db.get(QuestionnaireClassificationRule, ans.classification_id)
            if crow:
                cls_code = crow.code
        from app.api.tag_recommend import compute_recommend_for_submit
        recommend_goods, recommend_click_mode, recommend_display_count = await compute_recommend_for_submit(
            db, tpl.id, cls_code
        )
    except Exception as e:  # noqa: BLE001
        import logging as _l
        _l.getLogger(__name__).warning("recommend compute failed: %s", e)

    # 当 AI 追问开关关闭时，清空 active_followup
    if not ai_followup_enabled:
        active_followup = None

    return {
        "answer_id": ans.id,
        "template_id": tpl.id,
        "card": {
            "template_code": tpl.code,
            "template_name": tpl.name,
            "summary_text": summary_text,
            "fields": fields,
            "icon": icon,
        },
        "ai_prompt_hint": tpl.ai_opening,
        "classification_id": classification_id,
        # [PRD-TCM-DRAWER-V12 2026-05-20] 主动追问内容（前端在结果页关闭后追加到对话流）
        "active_followup": active_followup,
        # [PRD-TAG-RECOMMEND-V1 2026-05-20] 三段式结果呈现配置 + 推荐数据
        "result_display_mode": result_display_mode,
        "ai_followup_enabled": ai_followup_enabled,
        "recommend_click_mode": recommend_click_mode,
        "recommend_display_count": recommend_display_count,
        "recommend_goods": recommend_goods,
    }


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
#  [PRD-TCM-DRAWER-V12 2026-05-20] AI 主动追问接口
# ════════════════════════════════════════


@router.get("/answers/{answer_id}/follow-up")
async def get_answer_follow_up(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回完成问卷后的 AI 主动追问文案（供 h5 在结果页关闭后插入消息流使用）。

    - 受按钮配置 `ai_reference_active` 控制（默认 true）
    - 仅 questionnaire 类按钮关联此模板时才返回文案，否则 enabled=false
    """
    ans = await db.get(QuestionnaireAnswer, answer_id)
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答题记录不存在")
    tpl = await db.get(QuestionnaireTemplate, ans.template_id)
    main_type: Optional[str] = None
    if ans.classification_id:
        cls = await db.get(QuestionnaireClassificationRule, ans.classification_id)
        if cls:
            main_type = cls.name
    if not main_type and isinstance(ans.dimension_scores, dict) and ans.dimension_scores:
        try:
            main_type = max(
                ans.dimension_scores.items(),
                key=lambda x: float(x[1] or 0),
            )[0]
        except Exception:  # noqa: BLE001
            main_type = None

    # 查关联按钮的 ai_reference_active 开关
    enabled = True
    try:
        btn_rows = (
            await db.execute(
                select(ChatFunctionButton).where(
                    ChatFunctionButton.questionnaire_template_id == ans.template_id,
                )
            )
        ).scalars().all()
        if btn_rows:
            enabled = any(b.ai_reference_active is not False for b in btn_rows)
    except Exception:  # noqa: BLE001
        enabled = True

    if not enabled or not main_type:
        return {"enabled": False, "message": "", "main_type": main_type}

    msg = f"您想了解 {main_type} 的具体调理方法吗？"
    return {
        "enabled": True,
        "message": msg,
        "main_type": main_type,
        "template_id": ans.template_id,
        "template_code": tpl.code if tpl else None,
    }


# ════════════════════════════════════════
#  管理端 API（模板/题目/分型/推荐 CRUD）
# ════════════════════════════════════════


@admin_router.get("/templates")
async def admin_list_templates(
    page: int = Query(1, ge=1),
    # [PRD-TCM-DRAWER-V12-BUG1 2026-05-20] 下拉选项类场景需要更大上限，
    # 由 le=100 放宽至 le=500，避免前端拉取全量模板时被 422 拦截
    page_size: int = Query(20, ge=1, le=500),
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
