from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class SystemMessageResponse(BaseModel):
    id: int
    message_type: str
    recipient_user_id: int
    sender_user_id: Optional[int] = None
    sender_nickname: Optional[str] = None
    title: str
    content: str
    related_business_id: Optional[str] = None
    related_business_type: Optional[str] = None
    click_action: Optional[str] = None
    click_action_params: Optional[Any] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    items: List[SystemMessageResponse]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class AdminMessageCreate(BaseModel):
    recipient_user_ids: List[int]
    message_type: str
    title: str
    content: str


class AdminMessageStatsResponse(BaseModel):
    total: int
    unread: int
    type_counts: dict
