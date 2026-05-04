from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PointsRecordResponse(BaseModel):
    id: int
    user_id: int
    points: int
    type: str
    description: Optional[str] = None
    order_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SignInResponse(BaseModel):
    id: int
    user_id: int
    sign_date: date
    consecutive_days: int
    points_earned: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PointsMallItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    images: Optional[Any] = None
    type: str
    price_points: int
    stock: int
    status: str
    created_at: datetime
    is_exchangeable: Optional[bool] = None
    exchangeable_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PointsExchangeCreate(BaseModel):
    item_id: int
    quantity: int = 1
    shipping_info: Optional[Any] = None


class PointsExchangeResponse(BaseModel):
    id: int
    user_id: int
    item_id: int
    points_spent: int
    quantity: int
    status: str
    shipping_info: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberLevelResponse(BaseModel):
    id: int
    level_name: str
    min_points: int
    max_points: int
    discount_rate: float
    benefits: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PointsMallItemCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    type: Optional[str] = "virtual"
    price_points: int
    stock: Optional[int] = 0
    images: Optional[Any] = None
    status: Optional[str] = "active"


class PointsMallItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    price_points: Optional[int] = None
    stock: Optional[int] = None
    images: Optional[Any] = None
    status: Optional[str] = None
