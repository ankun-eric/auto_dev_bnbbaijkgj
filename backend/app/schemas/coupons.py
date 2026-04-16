from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CouponCreate(BaseModel):
    name: str
    type: str
    condition_amount: float = 0
    discount_value: float = 0
    discount_rate: float = 1.0
    scope: str = "all"
    scope_ids: Optional[Any] = None
    total_count: int = 0
    valid_start: Optional[datetime] = None
    valid_end: Optional[datetime] = None
    status: str = "active"


class CouponUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    condition_amount: Optional[float] = None
    discount_value: Optional[float] = None
    discount_rate: Optional[float] = None
    scope: Optional[str] = None
    scope_ids: Optional[Any] = None
    total_count: Optional[int] = None
    valid_start: Optional[datetime] = None
    valid_end: Optional[datetime] = None
    status: Optional[str] = None


class CouponResponse(BaseModel):
    id: int
    name: str
    type: str
    condition_amount: float
    discount_value: float
    discount_rate: float
    scope: str
    scope_ids: Optional[Any] = None
    total_count: int
    claimed_count: int
    used_count: int
    valid_start: Optional[datetime] = None
    valid_end: Optional[datetime] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCouponResponse(BaseModel):
    id: int
    user_id: int
    coupon_id: int
    status: str
    used_at: Optional[datetime] = None
    order_id: Optional[int] = None
    created_at: datetime
    coupon: Optional[CouponResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CouponClaimRequest(BaseModel):
    coupon_id: int


class CouponDistributeRequest(BaseModel):
    user_ids: list[int]
