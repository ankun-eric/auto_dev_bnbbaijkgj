from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NoticeCreate(BaseModel):
    content: str = Field(...)
    link_url: Optional[str] = Field(None, max_length=500)
    start_time: datetime
    end_time: datetime
    is_enabled: bool = Field(default=True)
    sort_order: int = Field(default=0)


class NoticeUpdate(BaseModel):
    content: Optional[str] = None
    link_url: Optional[str] = Field(None, max_length=500)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class NoticeResponse(BaseModel):
    id: int
    content: str
    link_url: Optional[str] = None
    start_time: datetime
    end_time: datetime
    is_enabled: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NoticePatchStatus(BaseModel):
    is_enabled: bool


class NoticeSortItem(BaseModel):
    id: int
    sort_order: int
