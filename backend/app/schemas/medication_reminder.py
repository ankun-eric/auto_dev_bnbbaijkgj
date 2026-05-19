"""[PRD-439] 用药提醒 Pydantic schemas。"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MedicationPlanBase(BaseModel):
    drug_name: str = Field(..., min_length=1, max_length=128)
    dosage: str = Field(..., min_length=1, max_length=64)
    schedule: List[str] = Field(..., min_length=1)
    note: Optional[str] = Field(None, max_length=256)
    enabled: bool = True
    patient_id: Optional[int] = None


class MedicationPlanCreate(MedicationPlanBase):
    pass


class MedicationPlanUpdate(BaseModel):
    drug_name: Optional[str] = Field(None, min_length=1, max_length=128)
    dosage: Optional[str] = Field(None, min_length=1, max_length=64)
    schedule: Optional[List[str]] = None
    note: Optional[str] = Field(None, max_length=256)
    enabled: Optional[bool] = None
    patient_id: Optional[int] = None


class MedicationPlanOut(BaseModel):
    id: int
    user_id: int
    patient_id: Optional[int] = None
    drug_name: str
    dosage: str
    schedule: List[str]
    note: Optional[str] = None
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TodayMedicationItem(BaseModel):
    plan_id: int
    drug_name: str
    dosage: str
    scheduled_time: str
    note: Optional[str] = None
    checked: bool = False
    checked_at: Optional[str] = None
    log_id: Optional[int] = None


class CheckRequest(BaseModel):
    plan_id: int
    scheduled_time: str = Field(..., min_length=4, max_length=8)
    log_date: Optional[date] = None


class CheckResponse(BaseModel):
    log_id: int
    checked_at: str


class UncheckRequest(BaseModel):
    log_id: int


# [PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛红点合并计数：扩展后向兼容的字段，
# 旧客户端仍可读 medication_unchecked / appointment_pending / total，新客户端用
# medication / order 嵌套对象（含 has_urgent / breakdown）。
class BadgeMedicationDetail(BaseModel):
    count: int = 0
    has_urgent: bool = False


class BadgeOrderBreakdown(BaseModel):
    pending_payment: int = 0
    pending_appointment: int = 0
    appointed: int = 0
    pending_use: int = 0
    partial_used: int = 0
    pending_receipt: int = 0


class BadgeOrderDetail(BaseModel):
    count: int = 0
    has_urgent: bool = False
    breakdown: BadgeOrderBreakdown = Field(default_factory=BadgeOrderBreakdown)


class BadgeResponse(BaseModel):
    # 旧字段：保留兼容
    medication_unchecked: int
    appointment_pending: int
    total: int
    # 新字段：合并计数 + 紧急标记 + 6 状态细分
    medication: BadgeMedicationDetail = Field(default_factory=BadgeMedicationDetail)
    order: BadgeOrderDetail = Field(default_factory=BadgeOrderDetail)


class AppointmentItem(BaseModel):
    order_id: int
    order_no: Optional[str] = None
    service_name: str
    appointed_at: Optional[str] = None
    location: Optional[str] = None
    status_text: str = "待核销"
    qrcode_url: Optional[str] = None
    verification_code: Optional[str] = None
    # [PRD-BELL-UNIFIED-V1] 抽屉订单条目扩展字段
    status: Optional[str] = None  # 6 种状态码（pending_payment / pending_appointment / appointed / pending_use / partial_used / pending_receipt）
    amount: Optional[str] = None
    quantity: Optional[int] = None
    spec: Optional[str] = None
    created_at: Optional[str] = None
    # 部分核销专用
    remaining_redeem_count: Optional[int] = None
    total_redeem_count: Optional[int] = None
    # 待收货专用
    tracking_company: Optional[str] = None
    tracking_number: Optional[str] = None
