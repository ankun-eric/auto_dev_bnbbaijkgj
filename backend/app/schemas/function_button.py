from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── ChatFunctionButton ────────────────


class ChatFunctionButtonCreate(BaseModel):
    name: str
    icon_url: Optional[str] = None
    button_type: str
    sort_weight: int = 0
    is_enabled: bool = True
    params: Optional[dict] = None


class ChatFunctionButtonUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    button_type: Optional[str] = None
    sort_weight: Optional[int] = None
    is_enabled: Optional[bool] = None
    params: Optional[dict] = None


class ChatFunctionButtonResponse(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    button_type: str
    sort_weight: int
    is_enabled: bool
    params: Optional[dict] = None
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
