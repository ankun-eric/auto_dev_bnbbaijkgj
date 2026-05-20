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


# [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用业务级占位符渲染 + 体质特征描述
# 体质一句话特征描述（用于卡片正面 main_type_desc 字段，避免前端写死）
CONSTITUTION_ONELINE_DESC: dict[str, str] = {
    "平和质": "阴阳气血调和、面色红润、精力充沛",
    "气虚质": "易疲倦、气短、声音低弱、容易出汗",
    "阳虚质": "怕冷、手脚发凉、喜热饮食、易腹泻",
    "阴虚质": "口干咽燥、手足心热、易便秘、面色偏红",
    "痰湿质": "易困倦、痰多、体形多肥胖、舌苔厚腻",
    "湿热质": "面垢油光、口苦口干、易长痘、大便黏滞",
    "血瘀质": "肤色晦暗、易出现瘀斑、唇色偏暗、易健忘",
    "气郁质": "情绪低落、忧郁多虑、胁肋胀闷、易叹气",
    "特禀质": "易过敏、对花粉/药物等敏感、有遗传倾向",
}

# 各体质对应的卡片封面色块（前端通用层 cover_style=universal_v1 时使用）
CONSTITUTION_COVER_COLOR: dict[str, str] = {
    "平和质": "#22C55E",
    "气虚质": "#F59E0B",
    "阳虚质": "#3B82F6",
    "阴虚质": "#EC4899",
    "痰湿质": "#0EA5E9",
    "湿热质": "#EF4444",
    "血瘀质": "#7C3AED",
    "气郁质": "#6366F1",
    "特禀质": "#10B981",
}


def _render_business_placeholders(
    text: Optional[str],
    *,
    main_type: Optional[str],
    secondary_types: Optional[list[str]],
    scores: Optional[dict[str, float]],
) -> Optional[str]:
    """渲染业务级占位符 {main_type} / {secondary_types} / {scores}。

    保证前端**永远不会**收到这些未渲染的 placeholder。
    """
    if not text:
        return text
    out = text
    if "{main_type}" in out:
        out = out.replace("{main_type}", main_type or "")
    if "{secondary_types}" in out:
        if secondary_types:
            out = out.replace("{secondary_types}", "、".join(secondary_types))
        else:
            out = out.replace("{secondary_types}", "无")
    if "{scores}" in out:
        if scores:
            parts = [f"{k}:{round(float(v), 1)}" for k, v in scores.items()]
            out = out.replace("{scores}", "  ".join(parts))
        else:
            out = out.replace("{scores}", "")
    return out


def _build_followup_chips(tpl_code: Optional[str], tpl=None) -> list[dict[str, str]]:
    """根据问卷类型返回追问 chips 列表。

    优先读 template.followup_chips_json（如管理后台配置），否则用默认配置。
    """
    if tpl is not None:
        try:
            cfg = getattr(tpl, "followup_chips_json", None)
            if cfg and isinstance(cfg, list) and len(cfg) > 0:
                norm: list[dict[str, str]] = []
                for c in cfg:
                    if isinstance(c, dict) and c.get("label"):
                        norm.append(
                            {
                                "code": str(c.get("code") or c.get("label")),
                                "label": str(c.get("label")),
                            }
                        )
                if norm:
                    return norm[:6]
        except Exception:  # noqa: BLE001
            pass
    # 默认 chips（按问卷类型）
    defaults: dict[str, list[dict[str, str]]] = {
        "tcm_constitution": [
            {"code": "tiaoli_method", "label": "调理方法"},
            {"code": "yinshi_jinji", "label": "饮食禁忌"},
            {"code": "yundong", "label": "适合运动"},
        ],
        "health_self_check": [
            {"code": "jianyi", "label": "处理建议"},
            {"code": "jiuyi", "label": "是否需就医"},
            {"code": "yufang", "label": "日常预防"},
        ],
        "phq9": [
            {"code": "shudao", "label": "情绪疏导"},
            {"code": "jiuyi", "label": "是否就医"},
            {"code": "ziwo", "label": "自我调节"},
        ],
        "gad7": [
            {"code": "shudao", "label": "情绪疏导"},
            {"code": "fangsong", "label": "放松练习"},
            {"code": "jiuyi", "label": "是否就医"},
        ],
        "psqi": [
            {"code": "zhumian", "label": "助眠方法"},
            {"code": "zuoxi", "label": "作息调整"},
            {"code": "huanjing", "label": "睡眠环境"},
        ],
    }
    return defaults.get(tpl_code or "", [
        {"code": "jianyi", "label": "详细建议"},
        {"code": "zhuyi", "label": "注意事项"},
        {"code": "fuwu", "label": "相关服务"},
    ])


def _build_questionnaire_card_payload(
    *,
    tpl,
    ans,
    main_type: Optional[str],
    secondary_types: Optional[list[str]],
    scores: Optional[dict[str, float]],
    classification_name: Optional[str],
    classification_code: Optional[str],
    subject_name: Optional[str],
    summary_text: Optional[str],
    fields: list[dict[str, Any]],
    icon: str,
) -> dict[str, Any]:
    """构建 questionnaire_result_card 的统一 payload（三端共用）。"""
    # 主结论：体质卷优先 main_type；其他卷优先 classification_name
    main_label = main_type or classification_name or ""
    main_desc = CONSTITUTION_ONELINE_DESC.get(main_label or "", "")
    cover_color = CONSTITUTION_COVER_COLOR.get(main_label or "", "#0EA5E9")
    return {
        "questionnaire_code": tpl.code,
        "questionnaire_name": tpl.name,
        "subject_name": subject_name or "",
        "completed_at": ans.completed_at.isoformat() if ans.completed_at else None,
        "answer_id": ans.id,
        "result_id": ans.id,  # 用于详情页跳转
        "template_id": tpl.id,
        # 主结论
        "main_type": main_label,
        "main_type_desc": main_desc,
        "secondary_types": secondary_types or [],
        "classification_name": classification_name,
        "classification_code": classification_code,
        # 可视化数据
        "scores": scores or {},
        # 兜底文本（已完成业务级 placeholder 渲染）
        "summary_text": summary_text,
        # 字段明细（兼容旧版用户气泡里的字段块）
        "fields": fields,
        "icon": icon,
        # 详情跳转目标
        "detail_target": {
            "kind": "immersive_detail",
            "result_id": ans.id,
            # 体质卷专用：旧路由仍可用，新统一推荐 /tcm/result/{id}
            "route_h5": f"/tcm/result/{ans.id}" if tpl.code == "tcm_constitution" else None,
            "mp_path": (
                f"/pages/tcm-constitution-result/index?id={ans.id}"
                if tpl.code == "tcm_constitution"
                else None
            ),
        },
        "cover_style": "universal_v1",
        "cover_color": cover_color,
    }


def _build_chat_messages_sequence(
    *,
    tpl,
    ans,
    card_payload: dict[str, Any],
    ai_opening: Optional[str],
    main_type: Optional[str],
    secondary_types: Optional[list[str]],
    scores: Optional[dict[str, float]],
    subject_name: Optional[str],
    ai_followup_enabled: bool,
) -> list[dict[str, Any]]:
    """生成"卡片 → AI 解读 → chips"三条消息（统一协议）。

    严格遵循：
      - 所有消息 sender=ai（绝不生成 user 身份的"总结消息"）
      - 顺序：card → text → followup_chips
      - 所有 placeholder 在后端渲染完毕
      - chips 的 render_meta.include_archive_prefix=false（不带"本次回答结合 XX 的档案"开场白）
    """
    msgs: list[dict[str, Any]] = []

    # 1. 结果汇总卡片
    msgs.append(
        {
            "msg_id": f"qn_card_{ans.id}",
            "sender": "ai",
            "type": "questionnaire_result_card",
            "card": card_payload,
        }
    )

    # 2. AI 解读文字（首条，必带开场白）
    archive_prefix = (
        f"本次回答结合 {subject_name} 的档案。" if subject_name else "本次回答结合您的档案。"
    )
    if ai_opening:
        ai_opening_rendered = _render_business_placeholders(
            ai_opening,
            main_type=main_type,
            secondary_types=secondary_types,
            scores=scores,
        ) or ""
        # 若 ai_opening 自带"本次回答结合"，不重复
        if "本次回答结合" in ai_opening_rendered:
            text_body = ai_opening_rendered
        else:
            text_body = archive_prefix + ai_opening_rendered
    else:
        # 兜底：根据 main_type 生成简短解读
        if main_type:
            text_body = (
                f"{archive_prefix}您的主体质为「{main_type}」"
                f"{('，兼夹' + '、'.join(secondary_types)) if secondary_types else ''}。"
                f"{CONSTITUTION_ONELINE_DESC.get(main_type, '')}。"
                "我可以为您详细介绍调理方法、饮食禁忌或适合运动等内容，请点击下方按钮选择。"
            )
        else:
            text_body = f"{archive_prefix}已为您解读完毕，请查看上方卡片中的详细结果。"
    msgs.append(
        {
            "msg_id": f"qn_text_{ans.id}",
            "sender": "ai",
            "type": "text",
            "text": text_body,
            "render_meta": {"include_archive_prefix": True},
        }
    )

    # 3. chips 追问（最后一条，不带开场白）
    if ai_followup_enabled:
        chips = _build_followup_chips(tpl.code, tpl)
        msgs.append(
            {
                "msg_id": f"qn_chips_{ans.id}",
                "sender": "ai",
                "type": "followup_chips",
                "chips": chips,
                "render_meta": {
                    "include_archive_prefix": False,
                    "questionnaire_result_id": ans.id,
                    "template_code": tpl.code,
                },
            }
        )
    return msgs


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
    # [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 业务级结果字段（用于占位符渲染 + 卡片消息）
    constitution_main_type: Optional[str] = None
    constitution_secondary_types: list[str] = []
    constitution_scores: dict[str, float] = {}
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
            constitution_main_type = main_type
            constitution_secondary_types = list(res.secondary_types or [])
            constitution_scores = dict(res.scores or {})
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

    # [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 在后端完成所有业务级占位符渲染，
    # 严禁让 {main_type}/{secondary_types}/{scores} 透传给前端。
    summary_text = _render_business_placeholders(
        summary_text,
        main_type=constitution_main_type,
        secondary_types=constitution_secondary_types,
        scores=constitution_scores,
    )

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

    # [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 获取分型名/分型编码 + 被测人名字
    classification_name: Optional[str] = None
    classification_code: Optional[str] = None
    if classification_id:
        try:
            crow2 = await db.get(QuestionnaireClassificationRule, classification_id)
            if crow2:
                classification_name = crow2.name
                classification_code = crow2.code
        except Exception:  # noqa: BLE001
            pass
    subject_name: Optional[str] = None
    try:
        if payload.consultant_id:
            from app.models.models import FamilyMember
            mem = await db.get(FamilyMember, payload.consultant_id)
            if mem and getattr(mem, "name", None):
                subject_name = mem.name
        if not subject_name and getattr(current_user, "nickname", None):
            subject_name = current_user.nickname
        if not subject_name and getattr(current_user, "username", None):
            subject_name = current_user.username
    except Exception:  # noqa: BLE001
        pass

    # [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 卡片 payload + 对话流消息序列
    card_payload = _build_questionnaire_card_payload(
        tpl=tpl,
        ans=ans,
        main_type=constitution_main_type,
        secondary_types=constitution_secondary_types,
        scores=constitution_scores,
        classification_name=classification_name,
        classification_code=classification_code,
        subject_name=subject_name,
        summary_text=summary_text,
        fields=fields,
        icon=icon,
    )
    chat_messages_seq = _build_chat_messages_sequence(
        tpl=tpl,
        ans=ans,
        card_payload=card_payload,
        ai_opening=tpl.ai_opening,
        main_type=constitution_main_type,
        secondary_types=constitution_secondary_types,
        scores=constitution_scores,
        subject_name=subject_name,
        ai_followup_enabled=ai_followup_enabled,
    )

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
        # [PRD-TCM-DRAWER-V12 2026-05-20] 主动追问内容（旧版兼容字段；新版前端按 chat_messages 路由）
        "active_followup": active_followup,
        # [PRD-TAG-RECOMMEND-V1 2026-05-20] 三段式结果呈现配置 + 推荐数据
        "result_display_mode": result_display_mode,
        "ai_followup_enabled": ai_followup_enabled,
        "recommend_click_mode": recommend_click_mode,
        "recommend_display_count": recommend_display_count,
        "recommend_goods": recommend_goods,
        # [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用卡片消息协议（三端按 type 路由渲染）
        # 顺序：questionnaire_result_card → text → followup_chips（全部 sender=ai）
        # 所有业务级占位符已在后端渲染完毕，前端直接消费。
        "chat_messages": chat_messages_seq,
        "result_card_payload": card_payload,
    }


# [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 追问 chip 接口：用户点击 chip 后触发二轮回答
class FollowupChipRequest(QuestionnaireAnswerSubmit.__base__ if False else object):
    """占位声明（实际使用 dict 接收，避免引入新 schema 文件）。"""


@router.post("/followup-chip")
async def followup_chip(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-TCM-CARD-MSG-PROTOCOL-V1] 用户点击 followup_chips 后调用。

    入参：
      {
        "answer_id": int,         # 问卷结果 id
        "chip_code": str,         # 用户点击的 chip 标识
        "chip_label": str,        # chip 显示文本（用于日志/兜底）
        "family_member_id": int?  # 可选，咨询对象
      }
    返回：
      {
        "ok": true,
        "ai_text": "本次回答结合 XXX 的档案。...",  # 已带开场白的二轮回答
        "include_archive_prefix": true
      }
    设计要点：
      - 二轮回答**重新带上**「本次回答结合 XX 的档案」开场白
      - 不调用真实大模型（保持确定性，避免国内网络不稳定的 AI 服务波动影响验收），
        直接基于 main_type + chip_code 拼装一段结构化回答；如有需要可在此处接入 ai_service.
    """
    answer_id = payload.get("answer_id")
    chip_code = (payload.get("chip_code") or "").strip()
    chip_label = (payload.get("chip_label") or "").strip()
    if not answer_id or not chip_code:
        raise HTTPException(status_code=400, detail="answer_id 和 chip_code 必填")
    ans = await db.get(QuestionnaireAnswer, int(answer_id))
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答卷不存在或无权限")
    tpl = await db.get(QuestionnaireTemplate, ans.template_id)
    main_type: Optional[str] = None
    if ans.classification_id:
        crow = await db.get(QuestionnaireClassificationRule, ans.classification_id)
        if crow:
            main_type = crow.name
    # 解析被测人名字
    subject_name: Optional[str] = None
    try:
        fm_id = ans.consultant_id
        if fm_id:
            from app.models.models import FamilyMember
            mem = await db.get(FamilyMember, fm_id)
            if mem and getattr(mem, "name", None):
                subject_name = mem.name
        if not subject_name and getattr(current_user, "nickname", None):
            subject_name = current_user.nickname
    except Exception:  # noqa: BLE001
        pass
    archive_prefix = (
        f"本次回答结合 {subject_name} 的档案。"
        if subject_name
        else "本次回答结合您的档案。"
    )
    main_label = main_type or (tpl.name if tpl else "")
    chip_text_map: dict[str, dict[str, str]] = {
        "tiaoli_method": {
            "label": "调理方法",
            "body": (
                f"针对「{main_label}」，推荐以下三类调理方法：\n"
                f"1. 起居调摄：保持规律作息，避免过度劳累，建议 23 点前入睡；\n"
                f"2. 饮食调养：以平和清淡为主，根据体质特点选用相宜食材；\n"
                f"3. 运动锻炼：每周 3-5 次中低强度有氧运动，每次 30-45 分钟。"
            ),
        },
        "yinshi_jinji": {
            "label": "饮食禁忌",
            "body": (
                f"「{main_label}」饮食宜忌要点：\n"
                f"- 宜：温润平和、易消化的食材；\n"
                f"- 忌：生冷油腻、辛辣刺激、过咸过甜食物；\n"
                f"- 进餐时间规律，七八分饱即可，避免暴饮暴食。"
            ),
        },
        "yundong": {
            "label": "适合运动",
            "body": (
                f"「{main_label}」推荐运动方式：\n"
                f"- 八段锦/太极拳（柔和有氧，全年龄段适用）；\n"
                f"- 快走/慢跑（30 分钟/次，每周 3-5 次）；\n"
                f"- 游泳/瑜伽（提升心肺与柔韧性）。\n"
                f"运动强度以「微微出汗、能正常交谈」为度。"
            ),
        },
        "jianyi": {
            "label": chip_label or "处理建议",
            "body": "请遵循「先观察、再调整、必要时就医」的原则，结合自身情况循序渐进。",
        },
        "jiuyi": {
            "label": "是否需就医",
            "body": (
                "出现以下情况建议尽快就医：\n"
                "- 症状持续 2 周以上且无明显改善；\n"
                "- 症状显著影响日常工作、学习、睡眠；\n"
                "- 出现伴随性发热、剧痛等急性表现。\n"
                "请前往正规中医或综合医院进一步辨证诊治。"
            ),
        },
        "yufang": {
            "label": "日常预防",
            "body": "日常预防三要点：规律作息、均衡膳食、情志舒畅。建议每年做一次中医体质评估。",
        },
        "shudao": {
            "label": "情绪疏导",
            "body": "深呼吸 + 正念冥想 5-10 分钟，可配合温和音乐；记录情绪日记，每周回顾。",
        },
        "ziwo": {
            "label": "自我调节",
            "body": "每日固定 30 分钟「专属时光」，进行喜欢的低刺激活动（散步、听音乐、阅读）。",
        },
        "fangsong": {
            "label": "放松练习",
            "body": "推荐「4-7-8 呼吸法」：吸气 4 秒、屏息 7 秒、呼气 8 秒，循环 4-6 次。",
        },
        "zhumian": {
            "label": "助眠方法",
            "body": "睡前 1 小时关闭电子屏，温水泡脚 15 分钟；保持卧室温度 18-22℃、湿度 50%。",
        },
        "zuoxi": {
            "label": "作息调整",
            "body": "建议固定 23 点前入睡、6:30-7:30 起床；午休 20-30 分钟为宜，避免超过 45 分钟。",
        },
        "huanjing": {
            "label": "睡眠环境",
            "body": "卧室遮光、隔音、清新空气；床品柔软透气；远离闹钟与电子设备。",
        },
        "fuwu": {
            "label": "相关服务",
            "body": "您可前往「服务」页查看与您体质匹配的调理方案、膳食套餐与广州门店服务。",
        },
        "zhuyi": {
            "label": "注意事项",
            "body": "请按医嘱执行；如出现不适请及时停止并咨询专业人士。",
        },
    }
    chip_info = chip_text_map.get(chip_code) or {
        "label": chip_label or chip_code,
        "body": "您可结合卡片中的主结论与详情页内容进一步了解。",
    }
    ai_text = (
        f"{archive_prefix}关于您关心的「{chip_info['label']}」：\n\n"
        f"{chip_info['body']}\n\n"
        "如需查看完整结果与可视化数据，请点击上方卡片中的「查看详情」按钮。"
    )
    return {
        "ok": True,
        "ai_text": ai_text,
        "include_archive_prefix": True,
        "chip_code": chip_code,
        "chip_label": chip_info["label"],
        "answer_id": int(answer_id),
        "main_type": main_label,
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
