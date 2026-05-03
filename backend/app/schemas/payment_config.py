"""[支付配置 PRD v1.0] 支付通道 Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PaymentChannelBase(BaseModel):
    channel_code: str
    channel_name: str
    display_name: str
    platform: str  # miniprogram / app / h5
    provider: str  # wechat / alipay
    is_enabled: bool = False
    is_complete: bool = False
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    sort_order: int = 0


class PaymentChannelResponse(PaymentChannelBase):
    """GET 响应：敏感字段已掩码，普通字段也做尾 4 位掩码。"""
    id: int
    config_masked: dict = {}
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentChannelListItem(BaseModel):
    """列表精简项（管理员列表 + C 端 available-methods 共用部分）。"""
    channel_code: str
    channel_name: str
    display_name: str
    platform: str
    provider: str
    is_enabled: bool
    is_complete: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class PaymentChannelUpdate(BaseModel):
    """PUT 更新请求：所有字段可选；敏感字段值为空时保留原值，非空则加密替换。

    config 直接以 dict 形式提交，由后端按 channel_code 校验必填字段。
    """
    display_name: Optional[str] = None
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    sort_order: Optional[int] = None
    config: Optional[dict[str, Any]] = None


class PaymentChannelToggleRequest(BaseModel):
    enabled: bool


class PaymentTestResult(BaseModel):
    success: bool
    message: str
    detail: Optional[dict] = None


class AvailableMethodItem(BaseModel):
    """C 端 /api/pay/available-methods 单项。"""
    channel_code: str
    display_name: str
    provider: str
    sort_order: int = 0


class DefaultNotifyUrlResponse(BaseModel):
    notify_url: str
