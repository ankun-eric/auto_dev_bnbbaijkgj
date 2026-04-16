from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    appointment_data: Optional[Any] = None
    appointment_time: Optional[datetime] = None


class UnifiedOrderCreate(BaseModel):
    items: list[OrderItemCreate]
    payment_method: Optional[str] = None
    points_deduction: int = 0
    coupon_id: Optional[int] = None
    shipping_address_id: Optional[int] = None
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    product_name: str
    product_image: Optional[str] = None
    product_price: float
    quantity: int
    subtotal: float
    fulfillment_type: str
    verification_code: Optional[str] = None
    verification_qrcode_token: Optional[str] = None
    total_redeem_count: int
    used_redeem_count: int
    appointment_data: Optional[Any] = None
    appointment_time: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedOrderResponse(BaseModel):
    id: int
    order_no: str
    user_id: int
    total_amount: float
    paid_amount: float
    points_deduction: int
    payment_method: Optional[str] = None
    coupon_id: Optional[int] = None
    coupon_discount: float = 0
    status: str
    refund_status: str = "none"
    shipping_address_id: Optional[int] = None
    shipping_info: Optional[Any] = None
    tracking_number: Optional[str] = None
    tracking_company: Optional[str] = None
    notes: Optional[str] = None
    payment_timeout_minutes: int = 15
    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    auto_confirm_days: int = 7
    items: list[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedOrderPayRequest(BaseModel):
    payment_method: str = "wechat"


class UnifiedOrderCancelRequest(BaseModel):
    cancel_reason: Optional[str] = None


class UnifiedOrderReviewCreate(BaseModel):
    rating: int
    content: Optional[str] = None
    images: Optional[Any] = None


class UnifiedOrderRefundRequest(BaseModel):
    order_item_id: Optional[int] = None
    reason: Optional[str] = None
    refund_amount: Optional[float] = None


class ShipRequest(BaseModel):
    tracking_company: str
    tracking_number: str


class RefundActionRequest(BaseModel):
    admin_notes: Optional[str] = None


class RefundRequestResponse(BaseModel):
    id: int
    order_id: int
    order_item_id: Optional[int] = None
    user_id: int
    reason: Optional[str] = None
    refund_amount: float
    status: str
    admin_user_id: Optional[int] = None
    admin_notes: Optional[str] = None
    return_tracking_number: Optional[str] = None
    return_tracking_company: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderRedemptionResponse(BaseModel):
    id: int
    order_item_id: int
    redeemed_by_user_id: int
    store_id: Optional[int] = None
    redeemed_at: datetime
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SalesStatisticsResponse(BaseModel):
    total_orders: int = 0
    total_revenue: float = 0
    total_products_sold: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
