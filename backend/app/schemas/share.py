from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatShareCreate(BaseModel):
    session_id: int
    message_id: int


class ChatShareResponse(BaseModel):
    share_token: str
    share_url: str


class SharedMessageItem(BaseModel):
    role: str
    content: str
    created_at: Optional[datetime] = None


class SharedConversationResponse(BaseModel):
    session_title: Optional[str] = None
    session_type: Optional[str] = None
    user_nickname: Optional[str] = None
    user_message: SharedMessageItem
    ai_message: SharedMessageItem
    view_count: int = 0
    created_at: Optional[datetime] = None


class PosterGenerateRequest(BaseModel):
    session_id: int
    message_id: int
    ai_content_preview: Optional[str] = None


class ShareConfigResponse(BaseModel):
    logo_url: Optional[str] = None
    product_name: str = "宾尼小康"
    slogan: str = "AI健康管家"
    qr_code_url: Optional[str] = None
    background_color: str = "#ffffff"
    template: str = "default"


class ShareConfigUpdate(BaseModel):
    logo_url: Optional[str] = None
    product_name: Optional[str] = None
    slogan: Optional[str] = None
    qr_code_url: Optional[str] = None
    background_color: Optional[str] = None
    template: Optional[str] = None
