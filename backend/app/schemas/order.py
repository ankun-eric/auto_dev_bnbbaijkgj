from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    service_item_id: int
    quantity: int = 1
    payment_method: Optional[str] = None
    points_deduction: int = 0
    address: Optional[str] = None
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    order_status: Optional[str] = None
    payment_status: Optional[str] = None
    shipping_info: Optional[Any] = None
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    order_no: str
    user_id: int
    service_item_id: int
    quantity: int
    total_amount: float
    paid_amount: float
    points_deduction: int
    payment_method: Optional[str] = None
    payment_status: str
    order_status: str
    verification_code: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderReviewCreate(BaseModel):
    rating: int
    content: Optional[str] = None
    images: Optional[Any] = None


class OrderReviewResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    rating: int
    content: Optional[str] = None
    images: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefundRequest(BaseModel):
    reason: Optional[str] = None
