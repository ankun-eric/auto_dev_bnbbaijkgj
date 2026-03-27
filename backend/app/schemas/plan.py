from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class HealthPlanCreate(BaseModel):
    plan_name: str
    plan_type: Optional[str] = None
    content: Optional[Any] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class HealthTaskCreate(BaseModel):
    task_name: str
    task_type: Optional[str] = None
    task_time: Optional[str] = None
    reminder_time: Optional[str] = None
    points_reward: int = 0


class HealthPlanResponse(BaseModel):
    id: int
    user_id: int
    plan_name: str
    plan_type: Optional[str] = None
    content: Optional[Any] = None
    ai_generated: bool
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthTaskResponse(BaseModel):
    id: int
    plan_id: int
    user_id: int
    task_name: str
    task_type: Optional[str] = None
    task_time: Optional[str] = None
    reminder_time: Optional[str] = None
    status: str
    points_reward: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCheckInCreate(BaseModel):
    notes: Optional[str] = None


class AIGeneratePlanRequest(BaseModel):
    plan_type: Optional[str] = None
    goals: Optional[str] = None
