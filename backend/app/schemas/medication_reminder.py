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


class BadgeResponse(BaseModel):
    medication_unchecked: int
    appointment_pending: int
    total: int


class AppointmentItem(BaseModel):
    order_id: int
    order_no: Optional[str] = None
    service_name: str
    appointed_at: Optional[str] = None
    location: Optional[str] = None
    status_text: str = "待核销"
    qrcode_url: Optional[str] = None
    verification_code: Optional[str] = None
