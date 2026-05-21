"""[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
通用问卷架构 Schema 定义。

所有问卷类业务（健康自查、九型体质测评、睡眠测评、焦虑量表等）共用一套数据模型。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── QuestionnaireTemplate ────────────────


class QuestionnaireTemplateBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    intro_text: Optional[str] = None
    estimated_minutes: Optional[int] = 3
    allow_back: Optional[bool] = True
    shuffle_questions: Optional[bool] = False
    ai_prompt_template: Optional[str] = None
    ai_opening: Optional[str] = None
    report_layout: Optional[str] = "standard"
    status: Optional[int] = 1
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]
    result_summary_template: Optional[str] = None
    source: Optional[str] = "operator_created"
    # [PRD-TAG-RECOMMEND-V1 2026-05-20]
    result_display_mode: Optional[str] = "simple"
    ai_followup_enabled: Optional[bool] = True
    recommend_click_mode: Optional[str] = "drawer"
    recommend_display_count: Optional[int] = 6
    # [PRD-QN-CONTENT-V1 2026-05-20] 后台可配置 chips / CTA
    followup_chips_json: Optional[list[dict[str, Any]]] = None
    cta_list_json: Optional[list[dict[str, Any]]] = None
    # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] AI 追问关键字段
    key_field_codes: Optional[list[str]] = None


class QuestionnaireTemplateCreate(QuestionnaireTemplateBase):
    pass


class QuestionnaireTemplateUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    intro_text: Optional[str] = None
    estimated_minutes: Optional[int] = None
    allow_back: Optional[bool] = None
    shuffle_questions: Optional[bool] = None
    ai_prompt_template: Optional[str] = None
    ai_opening: Optional[str] = None
    report_layout: Optional[str] = None
    status: Optional[int] = None
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]
    result_summary_template: Optional[str] = None
    source: Optional[str] = None
    # [PRD-TAG-RECOMMEND-V1 2026-05-20]
    result_display_mode: Optional[str] = None
    ai_followup_enabled: Optional[bool] = None
    recommend_click_mode: Optional[str] = None
    recommend_display_count: Optional[int] = None
    # [PRD-QN-CONTENT-V1 2026-05-20] 后台可配置 chips / CTA
    followup_chips_json: Optional[list[dict[str, Any]]] = None
    cta_list_json: Optional[list[dict[str, Any]]] = None
    # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] AI 追问关键字段
    key_field_codes: Optional[list[str]] = None


class QuestionnaireTemplateResponse(QuestionnaireTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── QuestionnaireQuestion ────────────────


class QuestionnaireQuestionBase(BaseModel):
    template_id: int
    sort_order: int = 0
    question_type: str  # single_choice / multi_choice / text
    title: str
    subtitle: Optional[str] = None
    required: Optional[bool] = True
    options: Optional[list[dict[str, Any]]] = None
    dimension: Optional[str] = None
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 题目联动
    display_condition_json: Optional[dict[str, Any]] = None
    option_filter_json: Optional[dict[str, Any]] = None
    layout_hint: Optional[str] = "tag_grid"


class QuestionnaireQuestionCreate(QuestionnaireQuestionBase):
    pass


class QuestionnaireQuestionUpdate(BaseModel):
    sort_order: Optional[int] = None
    question_type: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    required: Optional[bool] = None
    options: Optional[list[dict[str, Any]]] = None
    dimension: Optional[str] = None
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]
    display_condition_json: Optional[dict[str, Any]] = None
    option_filter_json: Optional[dict[str, Any]] = None
    layout_hint: Optional[str] = None


class QuestionnaireQuestionResponse(QuestionnaireQuestionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── QuestionnaireClassificationRule ────────────────


class QuestionnaireClassificationRuleBase(BaseModel):
    template_id: int
    code: str
    name: str
    description: Optional[str] = None
    rule_type: str  # score_range / dimension_max / tag_match
    rule_config: dict[str, Any]
    sort_order: Optional[int] = 0


class QuestionnaireClassificationRuleCreate(QuestionnaireClassificationRuleBase):
    pass


class QuestionnaireClassificationRuleUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    rule_config: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None


class QuestionnaireClassificationRuleResponse(QuestionnaireClassificationRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── QuestionnaireRecommendation ────────────────


class QuestionnaireRecommendationBase(BaseModel):
    classification_id: int
    section_type: str  # product / service / store_service / coupon
    section_title: Optional[str] = None
    sort_order: Optional[int] = 0
    match_mode: Optional[str] = "sku_list"
    sku_ids: Optional[list[int]] = None
    tag_filters: Optional[list[str]] = None
    max_items: Optional[int] = 6


class QuestionnaireRecommendationCreate(QuestionnaireRecommendationBase):
    pass


class QuestionnaireRecommendationUpdate(BaseModel):
    section_type: Optional[str] = None
    section_title: Optional[str] = None
    sort_order: Optional[int] = None
    match_mode: Optional[str] = None
    sku_ids: Optional[list[int]] = None
    tag_filters: Optional[list[str]] = None
    max_items: Optional[int] = None


class QuestionnaireRecommendationResponse(QuestionnaireRecommendationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── QuestionnaireAnswer ────────────────


class QuestionnaireAnswerItem(BaseModel):
    """提交答题时单条答案项"""

    question_id: int
    value: Any  # int / list / str 等


class QuestionnaireAnswerSubmit(BaseModel):
    template_id: int
    consultant_id: Optional[int] = None
    answers: list[QuestionnaireAnswerItem]
    # [PRD-HSC-OPTIM-V3 2026-05-21] 前端从「咨询人胶囊」当前值取，落库 + 详情页直接展示
    subject_kind: Optional[str] = None  # 'self' | 'family'
    subject_member_id: Optional[int] = None
    subject_name: Optional[str] = None
    subject_relation: Optional[str] = None


class QuestionnaireAnswerResponse(BaseModel):
    id: int
    user_id: int
    template_id: int
    consultant_id: Optional[int] = None
    answers: Optional[list[dict[str, Any]]] = None
    total_score: Optional[float] = None
    dimension_scores: Optional[dict[str, Any]] = None
    classification_id: Optional[int] = None
    ai_summary: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QuestionnaireReportSection(BaseModel):
    """报告里某个推荐位的渲染数据"""

    section_type: str
    section_title: Optional[str] = None
    items: list[dict[str, Any]] = []


class QuestionnaireReportResponse(BaseModel):
    """通用问卷报告页接口返回结构"""

    answer_id: int
    template: dict[str, Any]
    classification: Optional[dict[str, Any]] = None
    ai_summary: Optional[str] = None
    dimensions: Optional[dict[str, Any]] = None
    recommendations: dict[str, list[dict[str, Any]]] = {}
    user_info: dict[str, Any] = {}
    answered_at: Optional[datetime] = None
