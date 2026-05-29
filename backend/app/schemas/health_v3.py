"""[PRD-468 2026-05-12] 健康档案改版 v3 Schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── 今日指标聚合 ────────────────────────────────────────────────────────

class MetricSnapshot(BaseModel):
    metric_type: str
    value: Optional[Dict[str, Any]] = None
    measured_at: Optional[str] = None
    source: Optional[str] = None
    is_abnormal: bool = False


class MedicationProgressSnapshot(BaseModel):
    """用药打卡当日进度。"""
    checked: int = 0
    total: int = 0
    has_overdue: bool = False


class TodayMetricsResponse(BaseModel):
    profile_id: int
    blood_pressure: MetricSnapshot
    blood_glucose: MetricSnapshot
    heart_rate: MetricSnapshot
    sleep: MetricSnapshot
    spo2: MetricSnapshot
    medication: MedicationProgressSnapshot


# ─── 单指标录入 ────────────────────────────────────────────────────────────

class MetricCreateRequest(BaseModel):
    value: Dict[str, Any] = Field(..., description="指标值（结构按 metric_type 不同而异）")
    measured_at: Optional[datetime] = None
    source: Optional[str] = "manual"


class MetricRecordOut(BaseModel):
    id: int
    profile_id: int
    metric_type: str
    value: Dict[str, Any]
    source: str
    measured_at: datetime
    created_at: datetime


class MetricHistoryResponse(BaseModel):
    metric_type: str
    trend_7days: List[Optional[float]] = Field(default_factory=list, description="近 7 日主指标点位（无数据为 null）")
    records: List[MetricRecordOut] = Field(default_factory=list)
    total: int = 0
    trend_dates: List[str] = Field(default_factory=list, description="近 7 日对应日期 YYYY-MM-DD（最右一日为今天）")
    trend_day_labels: List[str] = Field(default_factory=list, description="近 7 日 X 轴展示文案（如 周三/周四/.../今日）")
    # 血压专用：sbp/dbp 双曲线点位（与 trend_dates 对齐）
    trend_systolic: List[Optional[float]] = Field(default_factory=list, description="近 7 日收缩压均值，仅血压有效")
    trend_diastolic: List[Optional[float]] = Field(default_factory=list, description="近 7 日舒张压均值，仅血压有效")


# ─── 设备 ────────────────────────────────────────────────────────────────

class DeviceItem(BaseModel):
    id: Optional[int] = None
    device_type: str
    name: str
    status: str  # active | unbound | coming_soon
    last_sync_at: Optional[datetime] = None


class DevicesListResponse(BaseModel):
    items: List[DeviceItem]


class DeviceBindRequest(BaseModel):
    """启动 OAuth 绑定流程：本期返回模拟 auth_url 或直接占位绑定。"""
    device_id: Optional[str] = None


class DeviceBindResponse(BaseModel):
    bound: bool
    auth_url: Optional[str] = None
    message: Optional[str] = None


# ─── 用药计划聚合（含时间胶囊） ─────────────────────────────────────────

class MedicationTimeChip(BaseModel):
    scheduled_time: str
    checked: bool


class MedicationPlanCard(BaseModel):
    plan_id: int
    drug_name: str
    dosage: Optional[str] = None
    schedule: List[str] = []
    time_chips: List[MedicationTimeChip] = []
    weekly_completed: int = 0
    weekly_total: int = 0
    weekly_rate: float = 0.0


class MedicationPlanResponse(BaseModel):
    items: List[MedicationPlanCard] = []
    grace_minutes: int = 15
    notice: str = "漏打卡超 15 分钟将通知共管者"


# ─── 健康事件流 ────────────────────────────────────────────────────────

class HealthEventItem(BaseModel):
    id: int
    type: str
    title: str
    detail: Optional[str] = None
    occurred_at: datetime


class HealthEventsResponse(BaseModel):
    items: List[HealthEventItem] = []
    page: int = 1
    size: int = 20
    total: int = 0
