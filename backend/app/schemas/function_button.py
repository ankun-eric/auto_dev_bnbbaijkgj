from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# [Bug-470 2026-05-15] 把字面值 "无"/空白/明显非 URL 的脏数据规范成 None，
# 防止前端把它当作 <img src> / <a href> 用，触发 /ai-home/无/ 这类 404。
_PLACEHOLDER_VALUES = {"无", "无.", "none", "null", "n/a", "na", "暂无", "未设置", "未配置"}


def _sanitize_image_url(v: Any) -> Any:
    if v is None:
        return None
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return None
    if s.lower() in _PLACEHOLDER_VALUES or s in _PLACEHOLDER_VALUES:
        return None
    if s.startswith(("http://", "https://", "/", "./", "data:image/", "blob:")):
        return s
    # 既不是占位词也不是合法 URL，按"非法兜底"返回 None
    return None


def _sanitize_text(v: Any) -> Any:
    if v is None:
        return None
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return s
    if s in _PLACEHOLDER_VALUES or s.lower() in _PLACEHOLDER_VALUES:
        return ""
    return s


# ──────────────── ChatFunctionButton ────────────────


# [AI对话模式优化 PRD v1.0] 7 种按钮类型枚举（应用层校验）
# [PRD-PROMPT-CONFIG-V1 2026-05-14] 新增第 8 种：report_interpret（报告解读专属）
# [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新增 2 个新两大类：page_navigate / ai_function；
# 老的 9 种枚举继续被允许（兼容存量数据，启动期由迁移脚本回填新主类型 + 子类型）
ALLOWED_BUTTON_TYPES = {
    "digital_human_call",
    "photo_upload",
    "file_upload",
    "ai_chat_trigger",
    "external_link",
    "photo_recognize_drug",
    "quick_ask",
    "report_interpret",
    # [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 第 9 种：健康自查
    "health_self_check",
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 两大类合并主类型
    "page_navigate",
    "ai_function",
}

# [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] AI 功能子类型枚举
# [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 子类型按"交互形态"抽象，永久稳定 5 个
# 新增 questionnaire / image_capture；旧值（health_self_check/report_interpret/photo_upload/
# medicine_recognize）保留兼容期映射，运营在前端选择时只看到 5 个新选项。
ALLOWED_AI_FUNCTION_TYPES = {
    # 新 5 项稳定子类型（按交互形态划分）
    "questionnaire",
    "image_capture",
    "file_upload",
    "ai_dialog_trigger",
    "quick_ask",
    # 旧值（兼容期保留，待数据迁移完成后下线）
    "photo_upload",
    "report_interpret",
    "medicine_recognize",
    "health_self_check",
}

# [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 新 5 项子类型集合（仅前端展示用）
NEW_AI_FUNCTION_TYPES = {
    "questionnaire",
    "image_capture",
    "file_upload",
    "ai_dialog_trigger",
    "quick_ask",
}

# [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1] 图像采集子用途枚举
ALLOWED_CAPTURE_PURPOSES = {
    "identify_medicine",  # 识药（旧 medicine_recognize / photo_recognize_drug）
    "upload",             # 纯上传（旧 photo_upload）
    "interpret_report",   # 报告解读（旧 report_interpret）
}

# [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 未选档案策略枚举
ALLOWED_ARCHIVE_MISSING_STRATEGIES = {"use_default", "prompt_on_submit", "force_toast"}


class ChatFunctionButtonCreate(BaseModel):
    name: str
    icon_url: Optional[str] = None
    # [AICHAT-OPTIM-FIX-V1 F-01] 新的 Emoji 图标字段（取代 icon_url 作为图标主存储）
    icon: Optional[str] = None
    button_type: str
    sort_weight: int = 0
    is_enabled: bool = True
    # [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关（新增按钮默认两个都 OFF）
    is_recommended: bool = False
    is_capsule: bool = False
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 宫格/胶囊独立排序值
    grid_sort: Optional[int] = None
    capsule_sort: Optional[int] = None
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1] AI 功能子类型 + AI 开场白 + 页面跳转先弹卡片开关
    ai_function_type: Optional[str] = None
    ai_opening: Optional[str] = None
    pre_card_for_navigate: Optional[bool] = False
    params: Optional[dict] = None
    ai_reply_mode: Optional[str] = None
    photo_tip_text: Optional[str] = None
    max_photo_count: Optional[int] = None
    # [AI对话模式优化 PRD v1.0] 8 个新字段
    prompt_template_id: Optional[int] = None
    external_url: Optional[str] = None
    preset_prompt: Optional[str] = None
    auto_user_message: Optional[str] = ""
    card_title: Optional[str] = ""
    card_subtitle: Optional[str] = None
    card_cover_image: Optional[str] = None
    button_sub_desc: Optional[str] = None
    # [PRD-HEALTH-SELF-CHECK-V1] 4 个新字段（health_self_check 按钮专用）
    health_check_template_id: Optional[int] = None
    archive_missing_strategy: Optional[str] = "use_default"
    prompt_override_enabled: Optional[bool] = False
    prompt_override_text: Optional[str] = None
    # [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 3 个新字段
    # questionnaire_template_id：当 ai_function_type=questionnaire 时关联问卷模板
    # capture_purpose：当 ai_function_type=image_capture 时区分子用途
    # pre_card_enabled：是否启用对话内说明卡片（覆盖旧的 pre_card_for_navigate，对所有按钮类型统一可用）
    questionnaire_template_id: Optional[int] = None
    capture_purpose: Optional[str] = None
    pre_card_enabled: Optional[bool] = True
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态
    questionnaire_display_form: Optional[str] = "DRAWER_SCROLL"
    # [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 呈现配置三件套（新建按钮默认 auto_next_enabled=True）
    presentation_container: Optional[str] = "DRAWER"
    questions_per_page: Optional[int] = 1
    auto_next_enabled: Optional[bool] = True
    # [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标三选一
    pre_card_icon: Optional[str] = None
    pre_card_icon_type: Optional[str] = "default"
    # [PRD-TCM-DRAWER-V12 2026-05-20] 双触发开关 + AI 引用双开关 + 关键词列表
    trigger_by_keyword: Optional[bool] = True
    trigger_by_intent: Optional[bool] = True
    trigger_keywords: Optional[list] = None
    ai_reference_passive: Optional[bool] = True
    ai_reference_active: Optional[bool] = True


class ChatFunctionButtonUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    # [AICHAT-OPTIM-FIX-V1 F-01] 新的 Emoji 图标字段
    icon: Optional[str] = None
    button_type: Optional[str] = None
    sort_weight: Optional[int] = None
    is_enabled: Optional[bool] = None
    # [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关
    is_recommended: Optional[bool] = None
    is_capsule: Optional[bool] = None
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 宫格/胶囊独立排序值 + 子类型 + 开场白 + 跳转开关
    grid_sort: Optional[int] = None
    capsule_sort: Optional[int] = None
    ai_function_type: Optional[str] = None
    ai_opening: Optional[str] = None
    pre_card_for_navigate: Optional[bool] = None
    params: Optional[dict] = None
    ai_reply_mode: Optional[str] = None
    photo_tip_text: Optional[str] = None
    max_photo_count: Optional[int] = None
    # [AI对话模式优化 PRD v1.0] 8 个新字段
    prompt_template_id: Optional[int] = None
    external_url: Optional[str] = None
    preset_prompt: Optional[str] = None
    auto_user_message: Optional[str] = None
    card_title: Optional[str] = None
    card_subtitle: Optional[str] = None
    card_cover_image: Optional[str] = None
    button_sub_desc: Optional[str] = None
    # [PRD-HEALTH-SELF-CHECK-V1] 4 个新字段
    health_check_template_id: Optional[int] = None
    archive_missing_strategy: Optional[str] = None
    prompt_override_enabled: Optional[bool] = None
    prompt_override_text: Optional[str] = None
    # [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 3 个新字段
    questionnaire_template_id: Optional[int] = None
    capture_purpose: Optional[str] = None
    pre_card_enabled: Optional[bool] = None
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态
    questionnaire_display_form: Optional[str] = None
    # [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 呈现配置三件套
    presentation_container: Optional[str] = None
    questions_per_page: Optional[int] = None
    auto_next_enabled: Optional[bool] = None
    # [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标三选一
    pre_card_icon: Optional[str] = None
    pre_card_icon_type: Optional[str] = None
    # [PRD-TCM-DRAWER-V12 2026-05-20] 双触发开关 + AI 引用双开关 + 关键词列表
    trigger_by_keyword: Optional[bool] = None
    trigger_by_intent: Optional[bool] = None
    trigger_keywords: Optional[list] = None
    ai_reference_passive: Optional[bool] = None
    ai_reference_active: Optional[bool] = None


class ChatFunctionButtonResponse(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    # [AICHAT-OPTIM-FIX-V1 F-01] 新的 Emoji 图标字段
    icon: Optional[str] = None
    button_type: str
    sort_weight: int
    is_enabled: bool
    # [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关
    is_recommended: bool = False
    is_capsule: bool = False
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 宫格/胶囊独立排序值 + 子类型 + 开场白 + 跳转开关
    grid_sort: Optional[int] = 0
    capsule_sort: Optional[int] = 0
    ai_function_type: Optional[str] = None
    ai_opening: Optional[str] = None
    pre_card_for_navigate: Optional[bool] = False
    params: Optional[dict] = None
    ai_reply_mode: Optional[str] = None
    photo_tip_text: Optional[str] = None
    max_photo_count: Optional[int] = None
    # [AI对话模式优化 PRD v1.0] 8 个新字段
    prompt_template_id: Optional[int] = None
    external_url: Optional[str] = None
    preset_prompt: Optional[str] = None
    auto_user_message: Optional[str] = ""
    card_title: Optional[str] = ""
    card_subtitle: Optional[str] = None
    card_cover_image: Optional[str] = None
    button_sub_desc: Optional[str] = None
    # [PRD-HEALTH-SELF-CHECK-V1] 4 个新字段
    health_check_template_id: Optional[int] = None
    archive_missing_strategy: Optional[str] = None
    prompt_override_enabled: Optional[bool] = None
    prompt_override_text: Optional[str] = None
    # [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 3 个新字段
    questionnaire_template_id: Optional[int] = None
    capture_purpose: Optional[str] = None
    pre_card_enabled: Optional[bool] = None
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态
    questionnaire_display_form: Optional[str] = "DRAWER_SCROLL"
    # [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 呈现配置三件套
    presentation_container: Optional[str] = "DRAWER"
    questions_per_page: Optional[int] = 1
    auto_next_enabled: Optional[bool] = False
    # [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标三选一
    pre_card_icon: Optional[str] = None
    pre_card_icon_type: Optional[str] = "default"
    # [PRD-TCM-DRAWER-V12 2026-05-20] 双触发开关 + AI 引用双开关 + 关键词列表
    trigger_by_keyword: Optional[bool] = True
    trigger_by_intent: Optional[bool] = True
    trigger_keywords: Optional[list] = None
    ai_reference_passive: Optional[bool] = True
    ai_reference_active: Optional[bool] = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    # [Bug-470 2026-05-15] URL 类字段清理脏数据（如字面值"无"），避免前端把它当作 <img src>
    @field_validator("icon_url", "card_cover_image", "external_url", mode="before")
    @classmethod
    def _v_image_url(cls, v):
        return _sanitize_image_url(v)

    # 文本类字段清理：把"无"等占位词归一为空串
    @field_validator("card_subtitle", "button_sub_desc", "photo_tip_text", mode="before")
    @classmethod
    def _v_text(cls, v):
        return _sanitize_text(v)


# ──────────────── DigitalHuman ────────────────


class DigitalHumanCreate(BaseModel):
    name: str
    silent_video_url: str
    speaking_video_url: str
    tts_voice_id: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_enabled: bool = True


class DigitalHumanUpdate(BaseModel):
    name: Optional[str] = None
    silent_video_url: Optional[str] = None
    speaking_video_url: Optional[str] = None
    tts_voice_id: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_enabled: Optional[bool] = None


class DigitalHumanResponse(BaseModel):
    id: int
    name: str
    silent_video_url: str
    speaking_video_url: str
    tts_voice_id: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── VoiceCall ────────────────


class VoiceCallStartRequest(BaseModel):
    digital_human_id: Optional[int] = None
    chat_session_id: Optional[int] = None


class VoiceCallEndRequest(BaseModel):
    dialog_content: list = []


class VoiceCallMessageRequest(BaseModel):
    user_text: str


class VoiceCallMessageResponse(BaseModel):
    ai_text: str


class VoiceCallRecordResponse(BaseModel):
    id: int
    user_id: int
    digital_human_id: Optional[int] = None
    chat_session_id: Optional[int] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    dialog_content: Optional[list] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── VoiceServiceConfig ────────────────


class VoiceServiceConfigResponse(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoiceServiceConfigUpdate(BaseModel):
    config_key: str
    config_value: str


# ──────────────── 批量排序 ────────────────


class ButtonSortItem(BaseModel):
    id: int
    sort_weight: int


class ButtonSortRequest(BaseModel):
    items: list[ButtonSortItem]


# [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 单按钮原子排序操作
class ButtonSortActionRequest(BaseModel):
    """运营点击「置顶 / 上移 / 下移」时的请求体。

    - id        : 被操作按钮 ID
    - view_type : grid / capsule
    - action    : top / up / down
    """
    id: int
    view_type: str  # grid | capsule
    action: str  # top | up | down


# ──────────────── 图片识别请求 ────────────────


class ImageRecognizeRequest(BaseModel):
    image_url: str
