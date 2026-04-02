from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AIModelConfigCreate(BaseModel):
    provider_name: str = "OpenAI"
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    is_active: bool = False
    max_tokens: int = 4096
    temperature: float = 0.7


class AIModelConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class AIModelConfigResponse(BaseModel):
    id: int
    provider_name: str
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    is_active: bool
    max_tokens: int = 4096
    temperature: float = 0.7
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemConfigUpdate(BaseModel):
    config_value: str


class DashboardTrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    count: int


class DashboardRecentOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user: str
    service: str
    amount: float
    status: str
    time: str


class DashboardStats(BaseModel):
    """管理后台仪表盘；JSON 使用 camelCase 别名以匹配 admin-web。"""

    model_config = ConfigDict(populate_by_name=True)

    total_users: int = Field(default=0, serialization_alias="totalUsers")
    total_orders: int = Field(default=0, serialization_alias="totalOrders")
    total_revenue: float = Field(default=0, serialization_alias="totalRevenue")
    today_new_users: int = Field(default=0, serialization_alias="todayNewUsers")
    today_orders: int = Field(default=0, serialization_alias="todayOrders")
    today_revenue: float = Field(default=0, serialization_alias="todayRevenue")
    active_experts: int = Field(default=0, serialization_alias="activeExperts")
    total_articles: int = Field(default=0, serialization_alias="totalArticles")
    user_growth: list[DashboardTrendPoint] = Field(
        default_factory=list,
        serialization_alias="userGrowth",
    )
    order_trend: list[DashboardTrendPoint] = Field(
        default_factory=list,
        serialization_alias="orderTrend",
    )
    recent_orders: list[DashboardRecentOrder] = Field(
        default_factory=list,
        serialization_alias="recentOrders",
    )
    ai_calls: int = Field(default=0, serialization_alias="aiCalls")
