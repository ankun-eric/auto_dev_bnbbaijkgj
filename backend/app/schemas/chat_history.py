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
    # [BUG-461 (2026-05-11)] 抽屉「历史对话」列表新增咨询人字段，
    # 用于左侧 6 色圆点 + 关系文字渲染。
    # 关联为空时统一返回 self，本人时 family_member_id=None。
    family_member_id: Optional[int] = None
    family_member_relation: Optional[str] = "self"
    family_member_nickname: Optional[str] = None
    # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 新增会话状态/归档时间/最后活动时间
    status: Optional[str] = "archived"
    archived_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# [BUG-461 (2026-05-11)] AI 对话用户端建议项 / 创建会话 / 切咨询人新会话
class UserChatSessionCreate(BaseModel):
    """用户端创建新会话请求体。

    用于 Bug-C 修复：用户切换咨询人时，前端立即调用此接口创建
    挂在新咨询人下的新会话，而不是等到首条消息发送时才落库。

    [BUG-466 (2026-05-11)] 新增 archive_previous_session_id 字段：
    用户切换咨询对象或 6 小时自动切片时，前端在一次请求中同时
    完成「归档旧会话 + 创建新会话」，保证原子性，避免抽屉中出现
    "原会话消失"的中间态。后端会更新旧会话的 updated_at 为当前时间，
    使其在历史列表中按"最近活动"排序时立刻被提到顶部。
    """

    session_type: Optional[str] = "health_qa"
    title: Optional[str] = None
    family_member_id: Optional[int] = None
    # [BUG-466] 同请求归档旧会话；非法/越权 ID 会被静默忽略。
    archive_previous_session_id: Optional[int] = None


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
