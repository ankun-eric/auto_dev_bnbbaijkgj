from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    appointment_data: Optional[Any] = None
    appointment_time: Optional[datetime] = None
    sku_id: Optional[int] = None  # 多规格商品必填


class UnifiedOrderCreate(BaseModel):
    items: list[OrderItemCreate]
    payment_method: Optional[str] = None
    points_deduction: int = 0
    coupon_id: Optional[int] = None
    shipping_address_id: Optional[int] = None
    # [上门服务履约 PRD v1.0] 上门服务必填地址（fulfillment_type=on_site 时必传）
    service_address_id: Optional[int] = None
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
    redemption_code_status: Optional[str] = "active"
    redemption_code_expires_at: Optional[datetime] = None
    # [修改预约 Bug 修复 v1.0] 透传商品的预约模式给前端
    # 取值 none / date / time_slot / custom_form，前端据此联动隐藏时段块、跳转自定义表单等
    appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
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
    # [上门服务履约 PRD v1.0]
    service_address_id: Optional[int] = None
    service_address_snapshot: Optional[Any] = None
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
    has_reviewed: bool = False
    status_display: Optional[str] = None
    # PRD V2「核销订单状态体系优化」: 客户端展示用字段
    display_status: Optional[str] = None
    display_status_color: Optional[str] = None
    action_buttons: list[str] = []
    badges: list[str] = []
    store_name: Optional[str] = None
    # PRD「我的订单与售后状态体系优化」新增字段
    # aftersales_logical_status：4 值之一 pending / processing / completed / rejected / none
    aftersales_logical_status: Optional[str] = None
    aftersales_logical_label: Optional[str] = None
    # 评价时效：completed_at + 15 天，超期则前端置灰按钮
    review_deadline_at: Optional[datetime] = None
    review_expired: bool = False
    can_withdraw_refund: bool = False
    # [支付配置 PRD v1.0] 实际支付通道
    payment_channel_code: Optional[str] = None
    payment_display_name: Optional[str] = None
    payment_method_text: Optional[str] = None  # 形如 "微信支付（小程序）"
    items: list[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedOrderPayRequest(BaseModel):
    payment_method: str = "wechat"
    # [支付配置 PRD v1.0] 可选 channel_code（4 通道之一）
    channel_code: Optional[str] = None


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


class UnifiedOrderRefundCancelRequest(BaseModel):
    """PRD「我的订单与售后状态体系优化」F-13：用户撤销售后申请。"""
    cancel_reason: Optional[str] = None


class UnifiedOrderSetAppointmentRequest(BaseModel):
    """PRD V2：客户端设置预约时间（pending_appointment → appointed）。"""
    order_item_id: Optional[int] = None
    appointment_time: datetime
    appointment_data: Optional[Any] = None


class ShipRequest(BaseModel):
    tracking_company: str
    tracking_number: str


class RefundActionRequest(BaseModel):
    admin_notes: Optional[str] = None
    refund_amount: Optional[float] = None


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
    has_redemption: bool = False
    refund_amount_approved: Optional[float] = None
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
    total_refund_count: int = 0
    total_refund_amount: float = 0
    today_orders: int = 0
    today_revenue: float = 0
    today_refund_count: int = 0
    today_refund_amount: float = 0
    month_orders: int = 0
    month_revenue: float = 0
    month_refund_count: int = 0
    month_refund_amount: float = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class TrendItem(BaseModel):
    date: str
    order_count: int = 0
    revenue: float = 0
    refund_amount: float = 0


class RedemptionDetailItem(BaseModel):
    id: int
    order_item_id: int
    redeemed_at: datetime
    store_name: Optional[str] = None
    redeemed_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RefundDetailResponse(BaseModel):
    refund_request: RefundRequestResponse
    has_redemption: bool = False
    used_redeem_count: int = 0
    total_redeem_count: int = 0
    redemption_ratio: str = "0%"
    redemptions: list[RedemptionDetailItem] = []
    paid_amount: float = 0


class RefundReasonItem(BaseModel):
    reason: str
    count: int = 0
