"""[付费会员体系 PRD v1.1] Schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────── Plan ────────────────


class MembershipPlanCreate(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    price_monthly: float = 0
    price_yearly: Optional[float] = None
    ai_call_quota: int = 0   # v1.2 deprecated 字段，保留兼容
    ai_alert_quota: int = 0  # v1.2 deprecated 字段，保留兼容
    ai_remind_quota: int = 0  # AI 外呼提醒额度（次/月），-1=不限
    emergency_ai_call_count: int = 0  # [v1.2] 紧急 AI 呼叫额度，-1=不限
    max_guardians: int = 1  # 被绑定守护上限（前端不展示）
    max_managed: int = 10  # [v1.2] 守护他人上限（前端展示）
    point_multiplier: float = 1.0  # [v1.2] 积分翻倍
    discount_rate: float = 1.0
    benefits_desc: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class MembershipPlanUpdate(BaseModel):
    plan_code: Optional[str] = None
    name: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    ai_call_quota: Optional[int] = None
    ai_alert_quota: Optional[int] = None
    ai_remind_quota: Optional[int] = None
    emergency_ai_call_count: Optional[int] = None
    max_guardians: Optional[int] = None
    max_managed: Optional[int] = None
    point_multiplier: Optional[float] = None
    discount_rate: Optional[float] = None
    benefits_desc: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class MembershipPlanResponse(BaseModel):
    id: int
    plan_code: str
    name: str
    price_monthly: float
    price_yearly: Optional[float] = None
    ai_call_quota: int
    ai_alert_quota: int
    ai_remind_quota: int
    emergency_ai_call_count: int = 0
    max_guardians: int
    max_managed: int = 10
    point_multiplier: float = 1.0
    discount_rate: float
    benefits_desc: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── Free Quota ────────────────


class FreeMemberQuotaUpdate(BaseModel):
    ai_call_quota: Optional[int] = None
    ai_alert_quota: Optional[int] = None
    ai_remind_quota: Optional[int] = None
    emergency_ai_call_count: Optional[int] = None
    max_guardians: Optional[int] = None
    max_managed: Optional[int] = None
    benefits_desc: Optional[str] = None


class FreeMemberQuotaResponse(BaseModel):
    id: int
    ai_call_quota: int
    ai_alert_quota: int
    ai_remind_quota: int
    emergency_ai_call_count: int = 3
    max_guardians: int
    max_managed: int = 3
    benefits_desc: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── User Membership ────────────────


class UserMembershipResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    plan_name: Optional[str] = None
    plan_code: Optional[str] = None
    billing_cycle: str
    start_at: datetime
    expire_at: datetime
    status: str
    discount_rate: Optional[float] = None
    max_guardians: Optional[int] = None
    ai_call_quota: Optional[int] = None
    ai_alert_quota: Optional[int] = None
    ai_remind_quota: Optional[int] = None
    auto_renew: bool

    model_config = ConfigDict(from_attributes=True)


class MembershipMeResponse(BaseModel):
    """当前用户的会员状态简要信息（用户端使用）"""
    is_paid_member: bool
    plan_id: Optional[int] = None
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    expire_at: Optional[datetime] = None
    discount_rate: float = 1.0
    max_guardians: int = 1
    max_managed: int = 3
    ai_call_quota: int = 0
    ai_alert_quota: int = 0
    ai_remind_quota: int = 0
    emergency_ai_call_count: int = 3
    benefits_desc: Optional[str] = None


class MembershipSubscribeRequest(BaseModel):
    plan_id: int
    billing_cycle: str = "monthly"  # monthly / yearly


# ──────────────── Discount Calculation ────────────────


class DiscountCalcRequest(BaseModel):
    """收银台计算优惠的请求"""
    product_id: int
    quantity: int = 1
    user_points: Optional[int] = None  # 若不传则从当前用户积分余额读取


class DiscountOptionItem(BaseModel):
    """单个可用的优惠选项"""
    type: str  # member_discount / points_deduction / none
    label: str
    discount_amount: float  # 抵扣/折扣金额（正数）
    final_price: float       # 最终应付
    detail: Optional[str] = None
    use_points: Optional[int] = None  # 若是积分抵扣，使用的积分数量


class DiscountCalcResponse(BaseModel):
    """收银台优惠计算结果（v1.1：会员折扣 vs 积分抵扣 二选一）"""
    product_id: int
    quantity: int
    original_price: float       # 单价 * 数量（不打折）
    is_paid_member: bool
    user_points: int
    member_discount_eligible: bool
    points_deductible: bool
    options: list[DiscountOptionItem]    # 可选的优惠方式
    recommended: str            # 默认推荐：member_discount / points_deduction / none
