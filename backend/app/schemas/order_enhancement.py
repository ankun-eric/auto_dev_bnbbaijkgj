"""[订单系统增强 PRD v1.0] 时段切片预约 + 站内消息 + 订单列表附件元信息 等 schemas。"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────── 营业时间窗 ────────────────

class BusinessHourEntry(BaseModel):
    """单条营业时间窗"""
    weekday: int = Field(..., ge=-1, le=6, description="0=周一...6=周日；-1=日期例外")
    date_exception: Optional[date] = Field(None, description="weekday=-1 时必填")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    is_closed: bool = False


class BusinessHoursSaveRequest(BaseModel):
    """保存营业时间窗（按门店全量替换）"""
    store_id: int
    entries: List[BusinessHourEntry]


class BusinessHoursResponse(BaseModel):
    store_id: int
    entries: List[BusinessHourEntry]


# ──────────────── 并发上限 ────────────────

class ConcurrencyLimitSaveRequest(BaseModel):
    store_id: int
    store_max_concurrent: int = Field(..., ge=1, le=999, description="门店级同时段最大接单数")
    service_overrides: Optional[List["ServiceConcurrencyOverride"]] = None


class ServiceConcurrencyOverride(BaseModel):
    product_id: int
    max_concurrent_override: Optional[int] = Field(
        None, ge=1, le=999, description="服务级并发上限；不填或 None 表示继承门店级"
    )
    service_duration_minutes: Optional[int] = Field(None, ge=5, le=720, description="服务时长（分钟）")


# 解决前向引用
ConcurrencyLimitSaveRequest.model_rebuild()


# ──────────────── 时段查询 ────────────────

class AvailableSlotItem(BaseModel):
    """时段切片"""
    start_at: datetime
    end_at: datetime
    is_available: bool
    reason: Optional[str] = Field(None, description="不可用原因：occupied / past / out_of_business / capacity_full")


class AvailableSlotsResponse(BaseModel):
    product_id: int
    store_id: int
    duration_minutes: int
    date: date
    slots: List[AvailableSlotItem]


# ──────────────── 站内消息红点 ────────────────

class UnreadCountResponse(BaseModel):
    """红点：返回未读总数（按订单去重 + 总数）"""
    total_unread: int = Field(..., description="未读消息总条数")
    total_orders_with_unread: int = Field(..., description="有未读消息的订单数（可作为 Tab 红点的数字）")
    order_ids: List[int] = Field(default_factory=list, description="有未读消息的订单 ID 列表")


class MarkReadByOrderRequest(BaseModel):
    order_id: int


class NotificationItem(BaseModel):
    id: int
    user_id: int
    order_id: Optional[int] = None
    event_type: Optional[str] = None
    title: str
    content: Optional[str] = None
    type: str = "system"
    is_read: bool = False
    extra_data: Optional[dict] = None
    created_at: datetime
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 订单列表附件元信息 ────────────────

class OrderAttachmentMeta(BaseModel):
    """订单列表中的附件简要信息"""
    order_id: int
    image_count: int = 0
    pdf_count: int = 0
    image_thumbs: List[str] = Field(default_factory=list, description="前 3 张图片的缩略图 URL")
    total_count: int = 0


class OrderListAttachmentMetaRequest(BaseModel):
    """批量查询订单的附件元信息"""
    order_ids: List[int] = Field(..., min_length=1, max_length=200)
    order_source: str = Field("item", description="item=按订单项；unified=按订单整体")


class OrderListAttachmentMetaResponse(BaseModel):
    items: List[OrderAttachmentMeta]
