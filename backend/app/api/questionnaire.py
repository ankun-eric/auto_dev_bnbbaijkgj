"""[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
通用问卷 API：用户端 + 管理后台。

设计要点：
- 所有问卷类业务统一调用本组 API（不再为每个业务新增独立路由）
- 用户端：模板查询、答题提交、结果与报告查询
- 管理端：模板/题目/分型规则/推荐配置 CRUD
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_hsc_v3_logger = logging.getLogger("hsc_optim_v3")

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


# ─────────────────────────────────────────────────────────────────
# [BUG-HSC-FIX-V2 2026-05-21] B-6 + B-7：占位符全量目录
# 供后台编辑抽屉的"占位符速查表"使用，无权鉴权
# ─────────────────────────────────────────────────────────────────
@router.get("/placeholder-catalog")
async def get_placeholder_catalog():
    """返回 AI Prompt / 结果摘要等模板中支持的全量占位符清单。

    前端在所有问卷模板的编辑抽屉中展示这份"速查表"，便于运营复制粘贴。
    """
    from app.services.prompt_renderer import PLACEHOLDER_CATALOG

    return {
        "items": PLACEHOLDER_CATALOG,
        "unfilled_text": "未填写",
        "version": "v2-20260521",
    }


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
            # [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 呈现配置三件套
            "presentation_container": btn.presentation_container or "DRAWER",
            "questions_per_page": int(btn.questions_per_page or 1),
            "auto_next_enabled": bool(btn.auto_next_enabled),
        },
        "display_form": btn.questionnaire_display_form or "DRAWER_SCROLL",
        # [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 呈现配置在顶层也暴露一份，方便前端直接读
        "presentation_container": btn.presentation_container or "DRAWER",
        "questions_per_page": int(btn.questions_per_page or 1),
        "auto_next_enabled": bool(btn.auto_next_enabled),
        # [PRD-HSC-OPTIM-V3 2026-05-21] 结果详情页 CTA 按钮（按钮级配置，未开启则返回 null）
        "result_cta": (
            {
                "text": (btn.result_cta_text or "找医生咨询")[:32],
                "target_type": btn.result_cta_target_type or "H5_PATH",
                "target_value": btn.result_cta_target_value or "",
            }
            if bool(getattr(btn, "result_cta_enabled", False))
            else None
        ),
        "template": None,
        "questions": [],
    }
    # [PRD-HSC-OPTIM-V3 2026-05-21] 排查埋点：实际下发的 auto_next_enabled / 容器 / 每页题数
    try:
        _hsc_v3_logger.info(
            "[render-meta] button_id=%s auto_next_enabled=%s questions_per_page=%s container=%s",
            btn.id, bool(btn.auto_next_enabled), int(btn.questions_per_page or 1), btn.presentation_container,
        )
    except Exception:  # noqa: BLE001
        pass
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
            {"code": "jiaju", "label": "居家如何处理"},
            {"code": "zhuyi", "label": "注意事项"},
            {"code": "jiuyi", "label": "是否需要就医"},
        ],
        "phq9": [
            {"code": "shudao", "label": "情绪疏导方法"},
            {"code": "gaishan", "label": "改善建议"},
            {"code": "jiuyi", "label": "何时该求助"},
        ],
        "gad7": [
            {"code": "shudao", "label": "情绪疏导方法"},
            {"code": "gaishan", "label": "改善建议"},
            {"code": "jiuyi", "label": "何时该求助"},
        ],
        "psqi": [
            {"code": "zhumian", "label": "改善睡眠方法"},
            {"code": "yinshi", "label": "助眠饮食"},
            {"code": "zuoxi", "label": "睡眠习惯调整"},
        ],
    }
    return defaults.get(tpl_code or "", [
        {"code": "jianyi", "label": "详细建议"},
        {"code": "zhuyi", "label": "注意事项"},
        {"code": "fuwu", "label": "相关服务"},
    ])


# [PRD-QN-CONTENT-V1 2026-05-20] CTA 配置
def _build_cta_list(
    tpl_code: Optional[str],
    tpl=None,
    *,
    main_type: Optional[str] = None,
    extra_cta: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """根据问卷类型返回 CTA 按钮列表（最多 4 个）。

    优先级：
    1. 强制 CTA（如 PHQ-9 第 9 题 >=1 的心理援助热线）会被插入到列表最前
    2. template.cta_list_json（运营后台配置）
    3. 内置默认 CTA（按问卷 code）

    CTA 字段：{label, action, target_url, style}
    """
    result: list[dict[str, Any]] = []
    if extra_cta:
        for c in extra_cta:
            if isinstance(c, dict) and c.get("label"):
                result.append(dict(c))

    # 从 tpl.cta_list_json 读取运营配置
    cfg_cta: list[dict[str, Any]] = []
    if tpl is not None:
        try:
            cfg = getattr(tpl, "cta_list_json", None)
            if cfg and isinstance(cfg, list):
                for c in cfg:
                    if isinstance(c, dict) and c.get("label"):
                        cfg_cta.append(dict(c))
        except Exception:  # noqa: BLE001
            pass

    if not cfg_cta:
        defaults: dict[str, list[dict[str, Any]]] = {
            "tcm_constitution": [
                {"label": "为我生成体质调理计划", "action": "generate_health_plan",
                 "target_url": "/health-plan/generate?source=tcm", "style": "primary"},
                {"label": "推荐：相应体质茶饮/食补套装", "action": "open_shop",
                 "target_url": "/shop/category/tea?tag={main_type}", "style": "secondary"},
            ],
            "phq9": [
                {"label": "为我生成情绪疏导计划", "action": "generate_health_plan",
                 "target_url": "/health-plan/generate?source=phq9", "style": "primary"},
                {"label": "推荐：心理咨询服务 / 冥想课程", "action": "open_service",
                 "target_url": "/services/category/mental_health", "style": "secondary"},
            ],
            "gad7": [
                {"label": "为我生成情绪疏导计划", "action": "generate_health_plan",
                 "target_url": "/health-plan/generate?source=gad7", "style": "primary"},
                {"label": "推荐：放松冥想课程", "action": "open_service",
                 "target_url": "/services/category/relaxation", "style": "secondary"},
            ],
            "psqi": [
                {"label": "为我生成助眠改善计划", "action": "generate_health_plan",
                 "target_url": "/health-plan/generate?source=psqi", "style": "primary"},
                {"label": "推荐：助眠产品 / 睡眠课程", "action": "open_shop",
                 "target_url": "/shop/category/sleep", "style": "secondary"},
            ],
            "health_self_check": [
                {"label": "为我生成针对性健康计划", "action": "generate_health_plan",
                 "target_url": "/health-plan/generate?source=health_self_check", "style": "primary"},
                {"label": "推荐：在线问诊 / 上门体检", "action": "open_service",
                 "target_url": "/services/category/consult", "style": "secondary"},
            ],
        }
        cfg_cta = defaults.get(tpl_code or "", [
            {"label": "为我生成健康计划", "action": "generate_health_plan",
             "target_url": "/health-plan/generate", "style": "primary"},
        ])

    # 渲染 {main_type} 占位符
    for c in cfg_cta:
        tu = c.get("target_url") or ""
        if "{main_type}" in tu:
            c = dict(c)
            c["target_url"] = tu.replace("{main_type}", main_type or "")
        result.append(c)

    return result[:4]


PHQ9_CRISIS_CTA = {
    "label": "立即拨打心理援助热线 400-161-9995",
    "action": "external_link",
    "target_url": "tel:400-161-9995",
    "style": "danger",
    "mandatory": True,
    "trigger": "phq9_q9>=1",
}


def _detect_phq9_crisis_from_qmap(
    tpl_code: Optional[str],
    answer_items: list[dict[str, Any]],
    question_map: dict[int, Any],
) -> bool:
    """[PRD-QN-CONTENT-V1] 检测 PHQ-9 第 9 题（自伤念头）是否 >= 1 分（基于题目 sort_order）"""
    if tpl_code != "phq9":
        return False
    for ai in answer_items:
        q = question_map.get(ai.get("question_id"))
        if q is None:
            continue
        try:
            if int(getattr(q, "sort_order", 0) or 0) == 9 and float(ai.get("score") or 0) >= 1:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


# ─────────────────────────────────────────────────────────────────
# [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
# 详情入口路由按 template.code + result_display_mode 派发，去掉硬编码
# ─────────────────────────────────────────────────────────────────


_ROUTE_H5_MAP = {
    "tcm_constitution": lambda ans_id: f"/tcm/result/{ans_id}",
    "health_self_check": lambda ans_id: f"/health-self-check/result/{ans_id}",
}
_MP_PATH_MAP = {
    "tcm_constitution": lambda ans_id: (
        f"/pages/tcm-constitution-result/index?id={ans_id}"
    ),
    "health_self_check": lambda ans_id: (
        f"/pages/health-self-check-result/index?id={ans_id}"
    ),
}


def _build_detail_target(tpl, ans) -> dict[str, Any]:
    """根据模板 code 与 result_display_mode 决定详情跳转目标。

    仅当 `result_display_mode == 'triple'` 时返回 route_h5 / mp_path；否则返回 None。
    """
    route_h5 = None
    mp_path = None
    mode = (getattr(tpl, "result_display_mode", None) or "simple").lower()
    if mode == "triple":
        code = tpl.code or ""
        fn = _ROUTE_H5_MAP.get(code)
        if fn:
            route_h5 = fn(ans.id)
        fnp = _MP_PATH_MAP.get(code)
        if fnp:
            mp_path = fnp(ans.id)
    return {
        "kind": "immersive_detail",
        "result_id": ans.id,
        "route_h5": route_h5,
        "mp_path": mp_path,
    }


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
    subject_kind: str = "self",
    subject_relation: Optional[str] = None,
) -> dict[str, Any]:
    """构建 questionnaire_result_card 的统一 payload（三端共用）。"""
    # 主结论：体质卷优先 main_type；其他卷优先 classification_name
    main_label = main_type or classification_name or ""
    main_desc = CONSTITUTION_ONELINE_DESC.get(main_label or "", "")
    cover_color = CONSTITUTION_COVER_COLOR.get(main_label or "", "#0EA5E9")

    # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 健康自查无分型/雷达，
    # main_type / main_type_desc 用首条主症状或 summary_text 兜底
    out_fields = fields
    if (tpl.code or "") == "health_self_check":
        # 优先把"主症状/部位"作为主类型
        field_map = {(f.get("label") or ""): f.get("value") or "" for f in fields}
        symptom_val = field_map.get("症状") or field_map.get("主症状") or ""
        part_val = field_map.get("部位") or ""
        if symptom_val and part_val:
            main_label = f"{part_val}·{symptom_val}".split("、")[0]
        elif symptom_val:
            main_label = str(symptom_val).split("、")[0]
        elif part_val:
            main_label = str(part_val).split("、")[0]
        else:
            main_label = "健康自查"
        main_desc = (summary_text or "").strip() or "完成本次自查，下方为关键症状信息与建议。"
        cover_color = "#0EA5E9"
        # 限制为 4 个关键字段，并标准化严重程度后缀
        preferred_keys = ["部位", "症状", "持续时间", "严重程度"]
        idx_map = {f.get("label") or "": f for f in fields}
        out_fields = []
        for k in preferred_keys:
            f = idx_map.get(k)
            if not f:
                continue
            v = f.get("value") or ""
            if k == "严重程度" and v and "/" not in str(v) and str(v).strip().isdigit():
                v = f"{v}/10"
            out_fields.append({"key": f.get("key") or k, "label": k, "value": v})

    # [BUG-HSC-FIX-V2 2026-05-21] B-2：subject 标签 = 本人 / 家人姓名（关系）
    if subject_kind == "family" and subject_name:
        if subject_relation:
            subject_label = f"{subject_name}（{subject_relation}）"
        else:
            subject_label = subject_name
    else:
        # 本人态：显示"本人"，避免显示登录名/手机号
        subject_label = "本人"
    return {
        "questionnaire_code": tpl.code,
        "questionnaire_name": tpl.name,
        "subject_name": subject_name or "",
        "subject_kind": subject_kind,
        "subject_relation": subject_relation or "",
        "subject_label": subject_label,
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
        "fields": out_fields,
        "icon": icon,
        # 详情跳转目标
        # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 去掉 tcm_constitution 硬编码：
        #   - 按 result_display_mode=='triple' 才生成 route_h5
        #   - 按 code 查 ROUTE_H5_MAP / MP_PATH_MAP
        "detail_target": _build_detail_target(tpl, ans),
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
    subject_kind: str = "self",
    subject_relation: Optional[str] = None,
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
    # [BUG-HSC-FIX-V2 2026-05-21] B-2：家人档案场景下，明确写"家人姓名（关系）"，
    # 不再统一兜底成"本人/您的档案"。
    if subject_kind == "family" and subject_name:
        _who = f"{subject_name}（{subject_relation}）" if subject_relation else subject_name
        archive_prefix = f"本次回答结合 {_who} 的健康档案。"
    elif subject_name and subject_kind == "self":
        archive_prefix = "本次回答结合本人的健康档案。"
    else:
        archive_prefix = "本次回答结合您的健康档案。"
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
    background_tasks: BackgroundTasks,
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

    # [PRD-HSC-OPTIM-V3 2026-05-21] 从前端「咨询人胶囊」获取 subject_*；若前端未传则按 consultant_id 反查
    _sub_kind = (payload.subject_kind or "").strip() or None
    _sub_member_id = payload.subject_member_id or payload.consultant_id
    _sub_name = (payload.subject_name or "").strip() or None
    _sub_relation = (payload.subject_relation or "").strip() or None
    if not _sub_kind:
        try:
            if payload.consultant_id:
                from app.models.models import FamilyMember as _FM2
                _m = await db.get(_FM2, payload.consultant_id)
                if _m:
                    _sub_kind = "self" if bool(getattr(_m, "is_self", False)) else "family"
                    if not _sub_name:
                        _sub_name = getattr(_m, "nickname", None)
                    if not _sub_relation:
                        _sub_relation = getattr(_m, "relationship_type", None)
        except Exception:  # noqa: BLE001
            pass
    if not _sub_kind:
        _sub_kind = "self"
    if not _sub_name:
        _sub_name = (
            getattr(current_user, "nickname", None)
            or getattr(current_user, "username", None)
            or ""
        )

    # 健康自查走异步解读；其他模板沿用同步（既有逻辑），ai_status='done'
    _is_hsc = (tpl.code or "") == "health_self_check"
    _initial_ai_status = "pending" if _is_hsc else "done"

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
        subject_kind=_sub_kind,
        subject_member_id=_sub_member_id,
        subject_name=_sub_name,
        subject_relation=_sub_relation,
        ai_status=_initial_ai_status,
    )
    db.add(ans)
    await db.flush()
    await db.refresh(ans)

    # [PRD-HSC-OPTIM-V3 2026-05-21] 健康自查：异步生成 AI 解读（先解读后跳转）
    if _is_hsc:
        background_tasks.add_task(_run_hsc_ai_interpretation, ans.id)

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
    # [BUG-HSC-FIX-V2 2026-05-21] B-2 修复：原来用 mem.name（字段不存在）导致取不到家人名，
    # 解读说明里"本次回答结合的对象"统一被兜底成本人 nickname。
    # 现在改用 FamilyMember.nickname；并区分 subject_kind/subject_relation，供前端展示。
    subject_name: Optional[str] = None
    subject_kind: str = "self"
    subject_relation: Optional[str] = None
    try:
        if payload.consultant_id:
            from app.models.models import FamilyMember
            mem = await db.get(FamilyMember, payload.consultant_id)
            if mem:
                # 是否本人档案（is_self FamilyMember 也是 family_members 表的一行）
                if bool(getattr(mem, "is_self", False)):
                    subject_kind = "self"
                else:
                    subject_kind = "family"
                # name 字段在 FamilyMember 模型中实际叫 nickname
                _nick = getattr(mem, "nickname", None)
                if _nick:
                    subject_name = _nick
                subject_relation = getattr(mem, "relationship_type", None)
        if not subject_name and getattr(current_user, "nickname", None):
            subject_name = current_user.nickname
        if not subject_name and getattr(current_user, "username", None):
            subject_name = current_user.username
    except Exception:  # noqa: BLE001
        pass

    # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 生成 AI 追问关键摘要
    # 仅注入模板配置的 key_field_codes 对应的字段，避免长问卷爆 token
    try:
        key_codes = list(getattr(tpl, "key_field_codes", None) or [])
        if key_codes:
            field_map = {(f.get("label") or ""): (f.get("value") or "") for f in fields}
            parts: list[str] = []
            for code in key_codes:
                v = field_map.get(code) or ""
                if not v:
                    continue
                if code == "严重程度" and "/" not in str(v) and str(v).strip().isdigit():
                    v = f"{v}/10"
                parts.append(f"{code}：{v}")
            if parts:
                ans.key_summary = "；".join(parts)[:200]
            else:
                ans.key_summary = (summary_text or "")[:200] or None
        else:
            ans.key_summary = (summary_text or "")[:200] or None
        await db.flush()
    except Exception as _e:  # noqa: BLE001
        import logging as _l
        _l.getLogger(__name__).warning("build key_summary failed: %s", _e)

    # [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 卡片 payload + 对话流消息序列
    # [BUG-HSC-FIX-V2 2026-05-21] B-2：透传 subject_kind / subject_relation
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
        subject_kind=subject_kind,
        subject_relation=subject_relation,
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
        subject_kind=subject_kind,
        subject_relation=subject_relation,
    )

    # [PRD-QN-CONTENT-V1 2026-05-20] 构建 CTA 列表（chat_messages 末尾追加 cta_buttons 消息）
    extra_cta: list[dict[str, Any]] = []
    crisis_flag = _detect_phq9_crisis_from_qmap(tpl.code, answer_items, question_map)
    if crisis_flag:
        # PHQ-9 第 9 题 >=1 → 强制最前面插入心理援助热线 CTA
        extra_cta.append(dict(PHQ9_CRISIS_CTA))
    cta_list = _build_cta_list(
        tpl.code,
        tpl,
        main_type=constitution_main_type or classification_name,
        extra_cta=extra_cta,
    )

    # 追加 CTA 消息到 chat_messages_seq
    if cta_list:
        chat_messages_seq.append({
            "msg_id": f"qn_cta_{ans.id}",
            "sender": "ai",
            "type": "cta_buttons",
            "cta_list": cta_list,
            "render_meta": {
                "include_archive_prefix": False,
                "questionnaire_result_id": ans.id,
                "template_code": tpl.code,
                "crisis": crisis_flag,
            },
        })

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
        # 顺序：questionnaire_result_card → text → followup_chips → cta_buttons（全部 sender=ai）
        # 所有业务级占位符已在后端渲染完毕，前端直接消费。
        "chat_messages": chat_messages_seq,
        "result_card_payload": card_payload,
        # [PRD-QN-CONTENT-V1 2026-05-20] CTA 列表（与 chat_messages 中末条 cta_buttons 一致，便于前端直接消费）
        "cta_list": cta_list,
        "phq9_crisis": crisis_flag,
    }


# ─────────────────────────────────────────────────────────────────
# [PRD-HSC-OPTIM-V3 2026-05-21] AI 解读异步生成 + 状态轮询 + 重试
# ─────────────────────────────────────────────────────────────────


_HSC_DEFAULT_HOME_CARE_TIPS = [
    "今日起减少高强度活动，保证 7-8 小时充足睡眠",
    "饮食清淡，避免辛辣、油炸、酒精与咖啡因",
    "根据症状性质选择对应方式：热敷/冷敷、休息、抬高患处",
    "每 2-4 小时给症状重新打分（0-10），观察趋势",
    "如确诊基础病，请按既往医嘱继续治疗",
]
_HSC_DEFAULT_RED_FLAGS = [
    "症状持续 2 周以上无改善",
    "症状明显影响日常工作、学习、睡眠",
    "出现剧烈疼痛、意识模糊、持续呕吐、剧烈头痛等急性表现",
    "服药后无效或出现皮疹/心悸/严重胃肠道反应",
    "老人 / 儿童 / 孕妇 / 慢病患者出现新症状",
]


def _hsc_archive_insufficient(member) -> bool:
    """判断家人档案是否信息较少：核心 3 项（年龄/性别/慢性病或主要疾病史）缺 ≥2 则视为不足。"""
    if member is None:
        return False
    try:
        miss = 0
        # 年龄优先看 birthday；其次 age 字段
        bd = getattr(member, "birthday", None)
        ageval = getattr(member, "age", None)
        if not bd and not ageval:
            miss += 1
        if not getattr(member, "gender", None):
            miss += 1
        chronic = (
            getattr(member, "chronic_diseases", None)
            or getattr(member, "medical_history", None)
            or getattr(member, "history", None)
        )
        if not chronic:
            miss += 1
        return miss >= 2
    except Exception:  # noqa: BLE001
        return False


async def _run_hsc_ai_interpretation(answer_id: int) -> None:
    """健康自查 AI 解读异步任务：填充 ai_full_interpretation / home_care_tips_json /
    red_flag_signals_json，并把 ai_status 置为 done / failed。

    现版采用确定性模板（不调用外网 LLM），保证服务器无外网时也能稳定完成。
    后续可在此处接入真实 LLM。
    """
    try:
        # 模拟少量耗时让前端体验"分析中"
        await asyncio.sleep(0.5)
        from app.core.database import async_session as _async_session_hsc_task
        async with _async_session_hsc_task() as db2:
            ans = await db2.get(QuestionnaireAnswer, answer_id)
            if not ans:
                return
            tpl = await db2.get(QuestionnaireTemplate, ans.template_id)
            ks = (ans.key_summary or "").strip()

            # 档案不足判定
            arch_insuff = False
            try:
                if (ans.subject_kind or "") == "family" and ans.subject_member_id:
                    from app.models.models import FamilyMember as _FM3
                    _m3 = await db2.get(_FM3, ans.subject_member_id)
                    arch_insuff = _hsc_archive_insufficient(_m3)
            except Exception:  # noqa: BLE001
                pass

            # [BUG-HSC-V31 2026-05-21] B-2 修复：标签格式「{relation}（{name}）」
            subj_label = ans.subject_name or ""
            if (ans.subject_kind or "") == "family" and ans.subject_relation:
                subj_label = f"{ans.subject_relation}（{ans.subject_name or ''}）"
            elif (ans.subject_kind or "") == "self":
                subj_label = "本人"

            interp = (
                f"本次结果由{('您' if (ans.subject_kind or 'self') == 'self' else subj_label + '的')}主诉的部位、症状、严重程度、持续时间综合得出。"
                + (f"关键症状：{ks}。" if ks else "")
                + "请结合「居家处理建议」尝试自我调节，并关注「就医警示」中的红线信号。"
                + "如症状持续或加重，请尽快前往正规医疗机构就诊。"
            )

            ans.ai_full_interpretation = interp
            ans.home_care_tips_json = list(_HSC_DEFAULT_HOME_CARE_TIPS)
            ans.red_flag_signals_json = list(_HSC_DEFAULT_RED_FLAGS)
            ans.archive_insufficient = arch_insuff
            # [BUG-HSC-V31 2026-05-21] 2-A 防护：写库前校验三大字段非空，
            # 防止"ai_status=done 但内容空"造成的"假 done"
            if not (
                (ans.ai_full_interpretation or "").strip()
                and ans.home_care_tips_json
                and ans.red_flag_signals_json
            ):
                ans.ai_status = "failed"
                ans.ai_failed_reason = "AI 解读关键字段为空"
            else:
                ans.ai_status = "done"
                ans.ai_failed_reason = None
            await db2.commit()
            _hsc_v3_logger.info(
                "[hsc-ai-task] answer_id=%s status=done arch_insuff=%s", answer_id, arch_insuff
            )
    except Exception as e:  # noqa: BLE001
        _hsc_v3_logger.exception("[hsc-ai-task] failed answer_id=%s err=%s", answer_id, e)
        # 失败回写
        try:
            from app.core.database import async_session as _async_session_hsc_task_fail
            async with _async_session_hsc_task_fail() as db3:
                ans = await db3.get(QuestionnaireAnswer, answer_id)
                if ans:
                    ans.ai_status = "failed"
                    ans.ai_failed_reason = str(e)[:255]
                    await db3.commit()
        except Exception:  # noqa: BLE001
            pass


@router.get("/answers/{answer_id}/ai-status")
async def get_answer_ai_status(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """轻量轮询接口：仅返回 ai_status / failed_reason。前端每 3s 调一次，最多 60s。"""
    ans = await db.get(QuestionnaireAnswer, answer_id)
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答题记录不存在")
    return {
        "answer_id": ans.id,
        "ai_status": (ans.ai_status or "done"),
        "failed_reason": ans.ai_failed_reason or "",
    }


@router.post("/answers/{answer_id}/retry-ai")
async def retry_answer_ai(
    answer_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """失败时手动重试 AI 解读。"""
    ans = await db.get(QuestionnaireAnswer, answer_id)
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答题记录不存在")
    ans.ai_status = "pending"
    ans.ai_failed_reason = None
    await db.commit()
    background_tasks.add_task(_run_hsc_ai_interpretation, ans.id)
    return {"ok": True, "ai_status": "pending"}


# [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 追问 chip 接口：用户点击 chip 后触发二轮回答
class FollowupChipRequest(QuestionnaireAnswerSubmit.__base__ if False else object):
    """占位声明（实际使用 dict 接收，避免引入新 schema 文件）。"""


# ─────────────────────────────────────────────────────────────────
# [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
# 健康自查 AI 追问结构化回答（基于 key_summary）
# ─────────────────────────────────────────────────────────────────


def _build_hsc_followup_text(
    *,
    archive_prefix: str,
    chip_code: str,
    chip_label: str,
    key_summary: str,
) -> str:
    """根据 chip 类型 + 关键症状摘要，生成三段式回答。

    - 不依赖外部大模型（保持确定性、避免网络抖动）
    - 自然引用 key_summary 中的关键症状字段
    """
    ks = key_summary or "本次自查关键症状信息（未获取到）"
    label = (chip_label or "").strip() or "针对性建议"
    code = (chip_code or "").lower()

    # 居家处理（jiaju）/ 注意事项（zhuyi）/ 是否需就医（jiuyi）三种主流向
    if code in ("jiuyi", "jiu_yi"):
        suggest_block = (
            "1. 立即评估：先安静休息，观察症状是否在 30 分钟内自行缓解；\n"
            "2. 自我量化：用 0-10 分给当前严重程度打分，若 ≥7 分建议尽快就诊；\n"
            "3. 资料准备：记录本次发作时间、诱因、伴随症状，便于医生快速判断。"
        )
        warn_block = (
            "- 出现意识改变、剧烈胸痛、呼吸困难、剧烈头痛伴呕吐 → 立即拨打 120；\n"
            "- 症状持续 ≥ 2 周仍无改善 → 尽快线下就诊；\n"
            "- 服药后无效或加重 → 停药并咨询医生。"
        )
        notice_block = (
            "- 就医前避免自行服用未经医生指导的处方药；\n"
            "- 携带过往体检报告与正在服用的药品清单；\n"
            "- 老年人、孕妇、慢病患者标准应放宽，建议尽早就诊。"
        )
    elif code in ("zhuyi", "zhu_yi"):
        suggest_block = (
            "1. 充分休息：保证 7-8 小时睡眠，避免熬夜与过度劳累；\n"
            "2. 饮食清淡：减少辛辣、油炸、过咸食物，多饮温水；\n"
            "3. 适度活动：每日 30 分钟低强度活动，避免剧烈运动加重不适。"
        )
        warn_block = (
            "- 症状每日加重 / 持续超过 1 周未缓解 → 建议就诊；\n"
            "- 出现新症状（发热、呕吐、剧痛、肢体麻木等）→ 立即就医；\n"
            "- 服药后出现皮疹、心悸、严重胃肠道反应 → 立即停药并就诊。"
        )
        notice_block = (
            "- 避免自行混合服用多种止痛/消炎药；\n"
            "- 慢病患者请按既往医嘱执行，勿自行停药；\n"
            "- 记录症状变化（频次、强度、诱因），下次问诊更高效。"
        )
    else:
        # 默认 jiaju / 居家如何处理
        suggest_block = (
            "1. 缓解症状：根据症状性质选择对应方式（如热敷/冷敷、休息、抬高患处）；\n"
            "2. 调整作息：今日先减少高强度活动，保证充足睡眠；\n"
            "3. 简单饮食干预：多饮温水、清淡饮食，避免酒精与咖啡因；\n"
            "4. 监测变化：每 2-4 小时给症状重新打分（0-10），观察变化趋势；\n"
            "5. 必要药物：在医生既往建议范围内可选择常用 OTC 药品，剂量勿超说明书。"
        )
        warn_block = (
            "- 居家观察 24-48 小时无改善或反而加重 → 建议就诊；\n"
            "- 出现剧烈疼痛、意识模糊、持续呕吐、明显出血等急性表现 → 立即就医；\n"
            "- 老人 / 儿童 / 孕妇 / 慢病患者出现新症状 → 不要拖延，尽早就诊。"
        )
        notice_block = (
            "- 不要自行联合多种处方药，避免相互作用；\n"
            "- 居家期间避免独居高风险行为（如开车、操作机械）；\n"
            "- 如确诊基础病，请按医嘱继续既有治疗方案；\n"
            "- 自查结果仅供参考，不能替代医生诊断。"
        )

    return (
        f"{archive_prefix}关于您关心的「{label}」，结合本次自查关键信息：\n"
        f"📌 {ks}\n\n"
        f"【针对性建议】\n{suggest_block}\n\n"
        f"【何时需就医】\n{warn_block}\n\n"
        f"【注意事项】\n{notice_block}"
    )


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
    # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 健康自查走结构化追问
    # 基于 ans.key_summary 输出【针对性建议】【何时需就医】【注意事项】三段
    if tpl and (tpl.code or "") == "health_self_check":
        ai_text = _build_hsc_followup_text(
            archive_prefix=archive_prefix,
            chip_code=chip_code,
            chip_label=chip_label,
            key_summary=(ans.key_summary or "").strip(),
        )
        return {
            "ok": True,
            "ai_text": ai_text,
            "include_archive_prefix": True,
            "chip_code": chip_code,
            "chip_label": chip_label or chip_code,
            "answer_id": int(answer_id),
            "main_type": main_label,
            "key_summary": ans.key_summary or "",
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


# [BUG-HSC-V31 2026-05-21] Bug 2-A 真正根因修复：
#   原 GET /answers/{answer_id} 与下方 get_answer_detail 路径完全冲突，
#   FastAPI 按"先注册先匹配"，导致下方丰富版（含 ai_full_interpretation /
#   home_care_tips / red_flag_signals / subject_label 的详情接口）永远走不到，
#   前端拿到的是这个简版 ORM 序列化结果——这就是用户实测「6 大区块全空」
#   和「咨询人识别为本人」的真正根因。
#   将简版 endpoint 改为 /answers/{answer_id}/raw，保留向下兼容；
#   让 /answers/{answer_id} 唯一指向 get_answer_detail。
@router.get(
    "/answers/{answer_id}/raw",
    response_model=QuestionnaireAnswerResponse,
)
async def get_answer_raw(
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


# ─────────────────────────────────────────────────────────────────
# [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
# 单个答卷详情：供 H5 详情页（健康自查结果页）拉取
# ─────────────────────────────────────────────────────────────────


@router.get("/answers/{answer_id}")
async def get_answer_detail(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回单次答卷的完整详情：题目 Q&A、AI 摘要、关键字段、模板基本信息等。

    用于健康自查 / 体质测评等三段式问卷的「查看详情」页面。
    """
    ans = await db.get(QuestionnaireAnswer, answer_id)
    if not ans or ans.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="答题记录不存在或无权限")
    tpl = await db.get(QuestionnaireTemplate, ans.template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 题目映射（用于把题号映射成题干）
    qrows = (
        await db.execute(
            select(QuestionnaireQuestion)
            .where(QuestionnaireQuestion.template_id == tpl.id)
            .order_by(QuestionnaireQuestion.sort_order.asc())
        )
    ).scalars().all()
    qmap = {q.id: q for q in qrows}

    # 整理 Q&A 列表
    qa_list: list[dict[str, Any]] = []
    for item in (ans.answers or []):
        qid = item.get("question_id")
        q = qmap.get(qid)
        v = item.get("value")
        if isinstance(v, list):
            display = "、".join(str(x) for x in v if x is not None and str(x) != "")
        else:
            display = "" if v is None else str(v)
        qa_list.append(
            {
                "question_id": qid,
                "sort_order": getattr(q, "sort_order", 0) if q else 0,
                "title": getattr(q, "title", "") if q else (item.get("title") or ""),
                "subtitle": getattr(q, "subtitle", None) if q else None,
                "dimension": item.get("dimension") or (getattr(q, "dimension", None) if q else None),
                "value": v,
                "value_display": display,
            }
        )
    qa_list.sort(key=lambda x: int(x.get("sort_order") or 0))

    # 分型
    classification_name: Optional[str] = None
    classification_code: Optional[str] = None
    if ans.classification_id:
        crow = await db.get(QuestionnaireClassificationRule, ans.classification_id)
        if crow:
            classification_name = crow.name
            classification_code = crow.code

    # [BUG-HSC-FIX-V2 2026-05-21] 详情页 subject 信息
    # [PRD-HSC-OPTIM-V3 2026-05-21] 优先用落库的 subject_*；缺则按 consultant_id 反查
    detail_subject_kind = (ans.subject_kind or "").strip() or "self"
    detail_subject_name: Optional[str] = (ans.subject_name or "").strip() or None
    detail_subject_relation: Optional[str] = (ans.subject_relation or "").strip() or None
    try:
        if (not detail_subject_name or not detail_subject_kind) and ans.consultant_id:
            from app.models.models import FamilyMember as _FM
            _mem = await db.get(_FM, ans.consultant_id)
            if _mem:
                if not ans.subject_kind:
                    detail_subject_kind = "self" if bool(getattr(_mem, "is_self", False)) else "family"
                if not detail_subject_name:
                    detail_subject_name = getattr(_mem, "nickname", None)
                if not detail_subject_relation:
                    detail_subject_relation = getattr(_mem, "relationship_type", None)
        if not detail_subject_name:
            detail_subject_name = getattr(current_user, "nickname", None) or getattr(current_user, "username", None)
    except Exception:  # noqa: BLE001
        pass
    if detail_subject_kind == "family" and detail_subject_name:
        # [BUG-HSC-V31 2026-05-21] B-2 修复：按需求文档显示「{relation}（{name}）」
        # 例：妈妈（张红）。relation 缺失时仅显示 name。
        detail_subject_label = (
            f"{detail_subject_relation}（{detail_subject_name}）"
            if detail_subject_relation
            else detail_subject_name
        )
    else:
        detail_subject_label = "本人"

    # AI 解读 / 居家建议 / 红线信号（健康自查不依赖大模型；按 key_summary 输出）
    # [PRD-HSC-OPTIM-V3 2026-05-21] 优先使用落库内容；ai_status=pending 时返回空让前端等待
    ai_conclusion = ""
    ai_full_interpretation = ""
    home_care_tips: list[str] = []
    red_flag_signals: list[str] = []
    if (tpl.code or "") == "health_self_check":
        ks = (ans.key_summary or "").strip()
        ai_conclusion = (
            f"已完成本次健康自查。{('关键症状：' + ks) if ks else ''}"
        ).strip()
        _stored_interp = (ans.ai_full_interpretation or "").strip()
        _stored_tips = ans.home_care_tips_json or []
        _stored_flags = ans.red_flag_signals_json or []
        if _stored_interp:
            ai_full_interpretation = _stored_interp
        elif (ans.ai_status or "done") == "done":
            ai_full_interpretation = (
                "本次结果由您主诉的部位、症状、严重程度、持续时间综合得出。"
                "请结合「居家处理建议」尝试自我调节，并关注「就医警示」中的红线信号。"
                "如症状持续或加重，请尽快前往正规医疗机构就诊。"
            )
        if isinstance(_stored_tips, list) and _stored_tips:
            home_care_tips = list(_stored_tips)
        elif (ans.ai_status or "done") == "done":
            home_care_tips = list(_HSC_DEFAULT_HOME_CARE_TIPS)
        if isinstance(_stored_flags, list) and _stored_flags:
            red_flag_signals = list(_stored_flags)
        elif (ans.ai_status or "done") == "done":
            red_flag_signals = list(_HSC_DEFAULT_RED_FLAGS)

    # 推荐商品（复用既有逻辑）
    recommend_goods: list[dict[str, Any]] = []
    try:
        from app.api.tag_recommend import compute_recommend_for_submit

        recommend_goods, _click_mode, _count = await compute_recommend_for_submit(
            db, tpl.id, classification_code
        )
    except Exception:  # noqa: BLE001
        recommend_goods = []

    # [PRD-HSC-OPTIM-V3 2026-05-21] 透传 result_cta：通过 answer→template→关联按钮 反查
    # 优先策略：找该模板对应的 questionnaire 类型按钮中第一个 result_cta_enabled=1 的；
    # 若都没开则返回 null（前端隐藏按钮）。
    result_cta_payload: Optional[dict[str, Any]] = None
    try:
        _btn_rows = (
            await db.execute(
                select(ChatFunctionButton).where(
                    ChatFunctionButton.questionnaire_template_id == tpl.id,
                    ChatFunctionButton.result_cta_enabled.is_(True),
                )
            )
        ).scalars().all()
        if _btn_rows:
            _btn0 = _btn_rows[0]
            result_cta_payload = {
                "text": (_btn0.result_cta_text or "找医生咨询")[:32],
                "target_type": _btn0.result_cta_target_type or "H5_PATH",
                "target_value": _btn0.result_cta_target_value or "",
            }
    except Exception:  # noqa: BLE001
        pass

    return {
        "answer_id": ans.id,
        "template_id": tpl.id,
        "template_code": tpl.code,
        "template_name": tpl.name,
        "created_at": ans.created_at.isoformat() if ans.created_at else None,
        "completed_at": ans.completed_at.isoformat() if ans.completed_at else None,
        "qa_list": qa_list,
        "classification_name": classification_name,
        "classification_code": classification_code,
        "key_summary": ans.key_summary or "",
        "ai_conclusion": ai_conclusion,
        "ai_full_interpretation": ai_full_interpretation,
        "home_care_tips": home_care_tips,
        "red_flag_signals": red_flag_signals,
        "recommend_goods": recommend_goods,
        # [BUG-HSC-FIX-V2 2026-05-21] B-2 详情页 subject 字段
        "subject_kind": detail_subject_kind,
        "subject_name": detail_subject_name or "",
        "subject_relation": detail_subject_relation or "",
        "subject_label": detail_subject_label,
        # [PRD-HSC-OPTIM-V3 2026-05-21] 异步解读状态 + 档案不足标志 + 结果页 CTA
        "ai_status": (ans.ai_status or "done"),
        "ai_failed_reason": ans.ai_failed_reason or "",
        "archive_insufficient": bool(getattr(ans, "archive_insufficient", False)),
        "result_cta": result_cta_payload,
    }


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
