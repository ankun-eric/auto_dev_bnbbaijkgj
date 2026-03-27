from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatSessionCreate(BaseModel):
    session_type: str
    title: Optional[str] = None
    family_member_id: Optional[int] = None


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    session_type: str
    title: Optional[str] = None
    family_member_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    file_url: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    message_type: str
    file_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIQueryRequest(BaseModel):
    content: str
    session_type: str = "health_qa"
    session_id: Optional[int] = None
    family_member_id: Optional[int] = None
