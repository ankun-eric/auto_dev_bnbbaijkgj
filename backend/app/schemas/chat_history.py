from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── 管理端 ────────────────


class AdminChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    message_type: str
    file_url: Optional[str] = None
    image_urls: Optional[list] = None
    file_urls: Optional[list] = None
    response_time_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminChatSessionItem(BaseModel):
    id: int
    user_id: int
    user_nickname: Optional[str] = None
    user_avatar: Optional[str] = None
    session_type: str
    title: Optional[str] = None
    first_message: Optional[str] = None
    message_count: int = 0
    model_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminChatSessionDetail(BaseModel):
    id: int
    user_id: int
    user_nickname: Optional[str] = None
    user_avatar: Optional[str] = None
    session_type: str
    title: Optional[str] = None
    model_name: Optional[str] = None
    message_count: int = 0
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    ip_location: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[AdminChatMessageItem] = []

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 用户端 ────────────────


class UserChatSessionItem(BaseModel):
    id: int
    session_type: str
    title: Optional[str] = None
    message_count: int = 0
    is_pinned: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionUpdate(BaseModel):
    title: str


class ChatSessionPinRequest(BaseModel):
    is_pinned: bool


# ──────────────── 分享 ────────────────


class SharedChatMessageItem(BaseModel):
    role: str
    content: str
    message_type: str
    file_url: Optional[str] = None
    image_urls: Optional[list] = None
    file_urls: Optional[list] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SharedChatResponse(BaseModel):
    title: Optional[str] = None
    session_type: str
    message_count: int = 0
    created_at: datetime
    messages: List[SharedChatMessageItem] = []

    model_config = ConfigDict(from_attributes=True)
