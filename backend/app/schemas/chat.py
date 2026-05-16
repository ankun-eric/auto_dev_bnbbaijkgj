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
    # [Bug-433 2026-05-09] 用户消息来源入口：text / voice / preset / voice_repair
    # 默认 text，便于在 chat_messages 表中区分会话首句的实际来源（文字/语音/预设按钮），
    # 用于排查"语音/预设按钮首句丢失"类回归与运营分析。非法值在路由层归一化为 'text'。
    source: Optional[str] = "text"
    # [BUG_FIX_拍照识药三联_20260516] 方案 E 新增字段：
    # - button_type：拍照识药 / 健康自查 / 报告解读等按钮入口类型；
    #   后端据此把消息路由到聊天内嵌识药引擎或其他专用流程。
    # - family_member_id：当前咨询人 ID（妈妈给孩子拍药时务必传入孩子的 ID）；
    #   决定档案上下文（剂量/禁忌/相互作用）来源，避免给儿童按成人剂量。
    button_type: Optional[str] = None
    family_member_id: Optional[int] = None


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
