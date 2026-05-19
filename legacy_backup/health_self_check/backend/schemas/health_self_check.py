"""[PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查功能 Schema 定义。

包含：
- BodyPartDict（部位症状字典）的 CRUD Schema
- HealthCheckTemplate（问卷模板）的 CRUD Schema
- HealthSelfCheckStartRequest / Response（用户端提交问卷 → 触发 AI 流式回答）
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────── BodyPartDict ────────────────


class BodyPartDictCreate(BaseModel):
    name: str = Field(..., max_length=20, description="部位名称")
    icon: str = Field(..., max_length=255, description="部位图标 URL")
    symptoms: list[str] = Field(default_factory=list, description="症状字符串数组，至少 1 项")
    sort_order: int = 100
    enabled: bool = True


class BodyPartDictUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=20)
    icon: Optional[str] = Field(default=None, max_length=255)
    symptoms: Optional[list[str]] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class BodyPartDictResponse(BaseModel):
    id: int
    name: str
    icon: str
    symptoms: list[str] = Field(default_factory=list)
    sort_order: int = 100
    enabled: bool = True
    symptom_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── HealthCheckTemplate ────────────────


class BodyPartRef(BaseModel):
    """模板内引用一个部位，含排序。"""
    id: int
    sort: int = 1


class HealthCheckTemplateCreate(BaseModel):
    name: str = Field(..., max_length=30)
    description: Optional[str] = Field(default=None, max_length=200)
    body_parts: list[BodyPartRef] = Field(default_factory=list, description="勾选的部位顺序数组")
    duration_options: list[str] = Field(default_factory=list, description="持续时间档位")
    default_prompt: str = Field(..., description="默认 Prompt 模板（含占位符）")
    enabled: bool = True


class HealthCheckTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=30)
    description: Optional[str] = Field(default=None, max_length=200)
    body_parts: Optional[list[BodyPartRef]] = None
    duration_options: Optional[list[str]] = None
    default_prompt: Optional[str] = None
    enabled: Optional[bool] = None


class HealthCheckTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    body_parts: list[dict[str, Any]] = Field(default_factory=list)
    duration_options: list[str] = Field(default_factory=list)
    default_prompt: str
    enabled: bool = True
    reference_button_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthCheckTemplateDetail(HealthCheckTemplateResponse):
    """详情页：返回 body_parts 时附带完整 BodyPartDict 信息（含 name、icon、symptoms）。"""
    body_parts_detail: list[dict[str, Any]] = Field(default_factory=list)


# ──────────────── 用户端：健康自查提交 ────────────────


class HealthSelfCheckStartRequest(BaseModel):
    """用户端在 ai-home 抽屉中点「开始 AI 分析」时调用。"""

    button_id: int = Field(..., description="按钮 ID（用于读取按钮的 Prompt 覆盖配置）")
    template_id: int = Field(..., description="问卷模板 ID")
    archive_id: Optional[int] = Field(default=None, description="咨询档案 ID（家庭成员 ID 或本人 ID；本人时传 0/null）")
    body_part_id: int = Field(..., description="选定的部位 ID")
    symptoms: list[str] = Field(..., min_length=1, description="选定的症状列表")
    duration: str = Field(..., description="选定的持续时间档位")
    # [PRD-HSC-SSE-V1 2026-05-16] 用户补充的「症状描述」（自然语言），最长 50 字，非必填
    symptom_description: Optional[str] = Field(
        default=None, max_length=50,
        description="用户自然语言补充的症状描述，可选，≤ 50 字",
    )
    session_id: Optional[int] = Field(default=None, description="所属 ChatSession ID（如不传由后端创建/复用）")


class HealthSelfCheckCardPayload(BaseModel):
    """前端自查卡片气泡的 payload（也作为返回值给前端，用于消息体）。"""

    archive_id: Optional[int] = None
    archive_name: Optional[str] = None
    archive_age: Optional[int] = None
    archive_gender: Optional[str] = None
    body_part: dict[str, Any] = Field(default_factory=dict)
    symptoms: list[str] = Field(default_factory=list)
    duration: str = ""
    # [PRD-HSC-SSE-V1 2026-05-16] 卡片气泡中同步展示用户填写的症状描述（为空则前端不渲染该行）
    symptom_description: Optional[str] = None
    template_id: int = 0
    button_id: int = 0


class HealthSelfCheckStartResponse(BaseModel):
    """提交后返回：插入的用户气泡消息 ID + AI 气泡消息 ID + AI 回答全文（同步返回简化版）。"""

    session_id: int
    user_message_id: int
    ai_message_id: int
    ai_content: str
    card_payload: HealthSelfCheckCardPayload
