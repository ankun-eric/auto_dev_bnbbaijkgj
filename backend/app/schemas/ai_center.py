from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── 敏感词 ──

class SensitiveWordCreate(BaseModel):
    sensitive_word: str
    replacement_word: str


class SensitiveWordUpdate(BaseModel):
    sensitive_word: Optional[str] = None
    replacement_word: Optional[str] = None


class SensitiveWordResponse(BaseModel):
    id: int
    sensitive_word: str
    replacement_word: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 提示词配置 ──

class PromptConfigResponse(BaseModel):
    id: int
    chat_type: str
    display_name: str
    system_prompt: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptConfigUpdate(BaseModel):
    system_prompt: str


# ── 免责提示配置 ──

class DisclaimerConfigResponse(BaseModel):
    id: int
    chat_type: str
    display_name: str
    disclaimer_text: Optional[str] = None
    is_enabled: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisclaimerConfigUpdate(BaseModel):
    disclaimer_text: Optional[str] = None
    is_enabled: Optional[bool] = None
