"""[PRD-MED-HISTORY-V1] 用药提醒历史打卡记录 Pydantic schemas。"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CalendarDayOut(BaseModel):
    """日历月视图某一天的状态。"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    status: str = Field(..., description="fully_done / partial / missed / no_plan")


class CalendarResponse(BaseModel):
    """日历月视图响应。"""
    year: int
    month: int
    days: list[CalendarDayOut]


class RecordItemOut(BaseModel):
    """单条打卡记录详情。"""
    plan_id: int
    drug_name: str
    dosage: str = ""
    scheduled_time: str = Field(..., description="计划时间点 HH:MM")
    status: str = Field(..., description="done / supplement / missed / expired / not_yet")
    check_in_time: Optional[str] = Field(None, description="实际打卡时间 ISO8601")
    check_in_type: Optional[str] = Field(None, description="normal / supplement")
    can_supplement: bool = False


class RecordsResponse(BaseModel):
    """某日所有打卡记录详情响应。"""
    date: str
    records: list[RecordItemOut]


class SupplementRequest(BaseModel):
    """补打卡请求体。"""
    plan_id: int = Field(..., description="用药计划 ID (MedicationReminder.id)")
    check_in_date: str = Field(..., description="补打卡日期 YYYY-MM-DD")
    scheduled_time: str = Field(..., description="计划时间点 HH:MM")


class SupplementResponse(BaseModel):
    """补打卡成功响应。"""
    id: int
    plan_id: int
    check_in_date: str
    scheduled_time: str
    check_in_time: str
    check_in_type: str = "supplement"
