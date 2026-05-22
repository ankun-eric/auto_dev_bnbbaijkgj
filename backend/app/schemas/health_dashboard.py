"""[PRD-HEALTH-DASHBOARD-V1] 家人健康看板 Pydantic Schemas。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── 健康看板汇总 ───────────────────────────────────────────────────────

class HealthScoreDetails(BaseModel):
    blood_pressure_score: float = 0
    blood_sugar_score: float = 0
    heart_rate_score: float = 0
    medication_score: float = 0
    regularity_score: float = 0


class VitalItem(BaseModel):
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    fasting: Optional[float] = None
    postprandial: Optional[float] = None
    value: Optional[float] = None
    is_abnormal: bool = False
    recorded_at: Optional[str] = None


class LatestVitals(BaseModel):
    blood_pressure: Optional[VitalItem] = None
    blood_sugar: Optional[VitalItem] = None
    heart_rate: Optional[VitalItem] = None


class TodayEvent(BaseModel):
    time: str
    type: str
    title: str
    is_abnormal: Optional[bool] = None
    completed: Optional[bool] = None


class MedicationPeriodItem(BaseModel):
    name: str
    completed: bool = False


class MedicationPeriod(BaseModel):
    period: str
    label: str
    items: List[MedicationPeriodItem] = []


class MedicationSummary(BaseModel):
    completion_rate: float = 0
    periods: List[MedicationPeriod] = []


class CheckupSummary(BaseModel):
    latest_date: Optional[str] = None
    abnormal_items: List[str] = []
    next_checkup_days: Optional[int] = None
    next_followup_days: Optional[int] = None


class HealthDashboardResponse(BaseModel):
    member_id: int
    member_name: str = ""
    health_score: float = 0
    health_score_details: HealthScoreDetails = HealthScoreDetails()
    latest_vitals: LatestVitals = LatestVitals()
    today_events: List[TodayEvent] = []
    medication_summary: MedicationSummary = MedicationSummary()
    checkup_summary: CheckupSummary = CheckupSummary()


# ─── 健康趋势 ──────────────────────────────────────────────────────────

class BloodPressureTrend(BaseModel):
    date: str
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    is_abnormal: bool = False


class BloodSugarTrend(BaseModel):
    date: str
    fasting: Optional[float] = None
    postprandial: Optional[float] = None
    is_abnormal: bool = False


class HeartRateTrend(BaseModel):
    date: str
    value: Optional[int] = None
    is_abnormal: bool = False


class NormalRanges(BaseModel):
    blood_pressure: Dict[str, List[float]] = {
        "systolic": [90, 139],
        "diastolic": [60, 89],
    }
    blood_sugar: Dict[str, List[float]] = {
        "fasting": [3.9, 6.1],
        "postprandial": [0, 7.8],
    }
    heart_rate: List[int] = [60, 100]


class HealthTrendsResponse(BaseModel):
    days: int = 7
    blood_pressure: List[BloodPressureTrend] = []
    blood_sugar: List[BloodSugarTrend] = []
    heart_rate: List[HeartRateTrend] = []
    normal_ranges: NormalRanges = NormalRanges()


# ─── 健康提醒 ──────────────────────────────────────────────────────────

class HealthReminderCreate(BaseModel):
    member_id: Optional[int] = None
    reminder_type: str = Field(..., pattern=r"^(followup|checkup|recheck)$")
    title: str = Field(..., max_length=200)
    hospital: Optional[str] = None
    department: Optional[str] = None
    scheduled_date: date
    recurrence: Optional[str] = Field(None, pattern=r"^(3months|6months|12months)$")
    notes: Optional[str] = None


class HealthReminderUpdate(BaseModel):
    title: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    scheduled_date: Optional[date] = None
    recurrence: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(pending|completed|cancelled)$")


class HealthReminderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: int
    member_id: Optional[int] = None
    reminder_type: str
    title: str
    hospital: Optional[str] = None
    department: Optional[str] = None
    scheduled_date: date
    recurrence: Optional[str] = None
    notes: Optional[str] = None
    status: str = "pending"
    source: str = "manual"
    related_metric: Optional[str] = None
    created_by: int
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HealthReminderListResponse(BaseModel):
    items: List[HealthReminderResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


# ─── 体检推荐 ──────────────────────────────────────────────────────────

class CheckupRecommendation(BaseModel):
    recommended_frequency: str = ""
    recommended_interval_months: int = 12
    last_checkup_date: Optional[str] = None
    days_since_last_checkup: Optional[int] = None
    next_recommended_date: Optional[str] = None
    age_group: str = ""
    suggestions: List[str] = []


# ─── 异常检查 ──────────────────────────────────────────────────────────

class HealthAlertCheckRequest(BaseModel):
    member_id: int
    metric_type: Optional[str] = None


class HealthAlertCheckResponse(BaseModel):
    checked: bool = True
    abnormal_found: bool = False
    alerts_created: int = 0
    recheck_reminders_created: int = 0
    details: List[Dict[str, Any]] = []
