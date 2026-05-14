from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── ChatFunctionButton ────────────────


# [AI对话模式优化 PRD v1.0] 7 种按钮类型枚举（应用层校验）
# [PRD-PROMPT-CONFIG-V1 2026-05-14] 新增第 8 种：report_interpret（报告解读专属）
ALLOWED_BUTTON_TYPES = {
    "digital_human_call",
    "photo_upload",
    "file_upload",
    "ai_chat_trigger",
    "external_link",
    "photo_recognize_drug",
    "quick_ask",
    "report_interpret",
}


class ChatFunctionButtonCreate(BaseModel):
    name: str
    icon_url: Optional[str] = None
    # [AICHAT-OPTIM-FIX-V1 F-01] 新的 Emoji 图标字段（取代 icon_url 作为图标主存储）
    icon: Optional[str] = None
    button_type: str
    sort_weight: int = 0
    is_enabled: bool = True
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


class ChatFunctionButtonUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    # [AICHAT-OPTIM-FIX-V1 F-01] 新的 Emoji 图标字段
    icon: Optional[str] = None
    button_type: Optional[str] = None
    sort_weight: Optional[int] = None
    is_enabled: Optional[bool] = None
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


class ChatFunctionButtonResponse(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    # [AICHAT-OPTIM-FIX-V1 F-01] 新的 Emoji 图标字段
    icon: Optional[str] = None
    button_type: str
    sort_weight: int
    is_enabled: bool
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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


# ──────────────── 图片识别请求 ────────────────


class ImageRecognizeRequest(BaseModel):
    image_url: str
