from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatSessionCreate(BaseModel):
    # [Bug-419 2026-05-08] session_type 改为可选并提供默认值兜底，避免任何客户端
    # 字段疏漏导致 422 必现。后端在路由层会进一步校验合法枚举值，非法值兜底为 health_qa。
    session_type: Optional[str] = "health_qa"
    title: Optional[str] = None
    family_member_id: Optional[int] = None
    symptom_info: Optional[dict] = None
    # [Bug-419 兼容字段] H5 早期实现误将 family_member_id 写为 member_id，此处显式
    # 接收旧字段并在路由层归一化为 family_member_id，避免老客户端版本继续 422。
    member_id: Optional[int] = None


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    session_type: str
    title: Optional[str] = None
    family_member_id: Optional[int] = None
    symptom_info: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    file_url: Optional[str] = None
    silent: Optional[bool] = False


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
