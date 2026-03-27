from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AIModelConfigCreate(BaseModel):
    provider_name: str
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    is_active: bool = False


class AIModelConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


class AIModelConfigResponse(BaseModel):
    id: int
    provider_name: str
    base_url: str
    model_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemConfigUpdate(BaseModel):
    config_value: str


class DashboardStats(BaseModel):
    total_users: int = 0
    total_orders: int = 0
    total_revenue: float = 0
    today_new_users: int = 0
    today_orders: int = 0
    today_revenue: float = 0
    active_experts: int = 0
    total_articles: int = 0
