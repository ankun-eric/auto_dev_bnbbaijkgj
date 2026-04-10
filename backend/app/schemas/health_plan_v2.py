from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── 用药提醒 ────────────────


class MedicationReminderCreate(BaseModel):
    medicine_name: str
    dosage: Optional[str] = None
    time_period: Optional[str] = None
    remind_time: Optional[str] = None
    notes: Optional[str] = None


class MedicationReminderUpdate(BaseModel):
    medicine_name: Optional[str] = None
    dosage: Optional[str] = None
    time_period: Optional[str] = None
    remind_time: Optional[str] = None
    notes: Optional[str] = None


class MedicationReminderResponse(BaseModel):
    id: int
    user_id: int
    medicine_name: str
    dosage: Optional[str] = None
    time_period: Optional[str] = None
    remind_time: Optional[str] = None
    notes: Optional[str] = None
    is_paused: bool
    status: str
    created_at: datetime
    today_checked: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class MedicationCheckInResponse(BaseModel):
    id: int
    reminder_id: int
    user_id: int
    check_in_date: date
    check_in_time: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 健康打卡 ────────────────


class HealthCheckInItemCreate(BaseModel):
    name: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    remind_times: Optional[List[str]] = None
    repeat_frequency: Optional[str] = "daily"
    custom_days: Optional[List[int]] = None


class HealthCheckInItemUpdate(BaseModel):
    name: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    remind_times: Optional[List[str]] = None
    repeat_frequency: Optional[str] = None
    custom_days: Optional[List[int]] = None


class HealthCheckInItemResponse(BaseModel):
    id: int
    user_id: int
    name: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    remind_times: Optional[Any] = None
    repeat_frequency: str
    custom_days: Optional[Any] = None
    status: str
    created_at: datetime
    today_completed: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class HealthCheckInRecordCreate(BaseModel):
    actual_value: Optional[float] = None


class HealthCheckInRecordResponse(BaseModel):
    id: int
    item_id: int
    user_id: int
    check_in_date: date
    actual_value: Optional[float] = None
    is_completed: bool
    check_in_time: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 模板分类 ────────────────


class PlanTemplateCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int
    preset_tasks: Optional[Any] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanTemplateCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    preset_tasks: Optional[Any] = None


class PlanTemplateCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    preset_tasks: Optional[Any] = None


# ──────────────── 推荐计划 ────────────────


class RecommendedPlanTaskResponse(BaseModel):
    id: int
    plan_id: int
    task_name: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendedPlanTaskCreate(BaseModel):
    task_name: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    sort_order: int = 0


class RecommendedPlanTaskUpdate(BaseModel):
    task_name: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    sort_order: Optional[int] = None


class RecommendedPlanResponse(BaseModel):
    id: int
    category_id: int
    name: str
    description: Optional[str] = None
    target_audience: Optional[str] = None
    duration_days: Optional[int] = None
    cover_image: Optional[str] = None
    is_published: bool
    sort_order: int
    created_at: datetime
    tasks: Optional[List[RecommendedPlanTaskResponse]] = None
    category_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RecommendedPlanCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None
    target_audience: Optional[str] = None
    duration_days: Optional[int] = None
    cover_image: Optional[str] = None
    is_published: bool = True
    sort_order: int = 0


class RecommendedPlanUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    duration_days: Optional[int] = None
    cover_image: Optional[str] = None
    sort_order: Optional[int] = None


# ──────────────── 用户计划 ────────────────


class UserPlanTaskResponse(BaseModel):
    id: int
    plan_id: int
    user_id: int
    task_name: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    sort_order: int
    created_at: datetime
    today_completed: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class UserPlanResponse(BaseModel):
    id: int
    user_id: int
    category_id: Optional[int] = None
    source_type: str
    recommended_plan_id: Optional[int] = None
    plan_name: str
    description: Optional[str] = None
    duration_days: Optional[int] = None
    current_day: int
    status: str
    start_date: Optional[date] = None
    created_at: datetime
    tasks: Optional[List[UserPlanTaskResponse]] = None
    category_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserPlanCreate(BaseModel):
    category_id: Optional[int] = None
    plan_name: str
    description: Optional[str] = None
    duration_days: Optional[int] = None
    tasks: Optional[List[RecommendedPlanTaskCreate]] = None


class UserPlanUpdate(BaseModel):
    plan_name: Optional[str] = None
    description: Optional[str] = None
    duration_days: Optional[int] = None
    status: Optional[str] = None


class UserPlanTaskCheckInCreate(BaseModel):
    actual_value: Optional[float] = None


class UserPlanTaskRecordResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    check_in_date: date
    actual_value: Optional[float] = None
    is_completed: bool
    check_in_time: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── AI 生成 ────────────────


class AIGeneratePlanV2Request(BaseModel):
    goals: Optional[str] = None


class AIGenerateCategoryPlanRequest(BaseModel):
    goals: Optional[str] = None


# ──────────────── 默认健康任务 ────────────────


class DefaultHealthTaskResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    category_type: Optional[str] = None
    template_category_id: Optional[int] = None
    sort_order: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DefaultHealthTaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    category_type: Optional[str] = None
    template_category_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True


class DefaultHealthTaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    category_type: Optional[str] = None
    template_category_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ──────────────── 今日待办 ────────────────


class TodayTodoItem(BaseModel):
    id: int
    name: str
    type: str
    source: str
    source_id: Optional[int] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    is_completed: bool = False
    remind_time: Optional[str] = None
    extra: Optional[Any] = None


class TodayTodoGroup(BaseModel):
    group_name: str
    group_type: str
    items: List[TodayTodoItem]
    completed_count: int = 0
    total_count: int = 0


class TodayTodoResponse(BaseModel):
    groups: List[TodayTodoGroup]
    total_completed: int = 0
    total_count: int = 0


# ──────────────── 统计 ────────────────


class CheckInStatisticsResponse(BaseModel):
    today_completed: int = 0
    today_total: int = 0
    today_progress: float = 0.0
    consecutive_days: int = 0
    weekly_data: Optional[List[Any]] = None
    monthly_data: Optional[List[Any]] = None
