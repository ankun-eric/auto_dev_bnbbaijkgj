"""[会员中心 PRD v1.0 对齐 - 2026-05-26] Schemas"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


# ──────────────── Plan ────────────────


class MembershipPlanCreate(BaseModel):
    """新增付费会员套餐入参（PRD v1.0）"""
    name: str = Field(..., min_length=1, max_length=50, description="套餐名称")
    description: Optional[str] = Field(None, max_length=255, description="套餐说明")
    price_month: Optional[float] = Field(None, ge=0, description="月价（30天），NULL=不支持月购")
    price_year: Optional[float] = Field(None, ge=0, description="年价（365天），NULL=不支持年购")
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径变更：
    # 语义：家庭守护成员总人数（**含主账号本人**），用户端原样展示。-1=不限
    max_managed: int = Field(4, description="家庭守护成员总人数（含本人，用户端原样展示），-1=不限")
    ai_outbound_call_count: int = Field(0, description="AI 外呼提醒（次/月），-1=不限")
    emergency_ai_call_count: int = Field(0, description="紧急 AI 呼叫（次/月），-1=不限")
    max_managed_by: int = Field(3, description="被管理人数上限，-1=不限")
    discount_rate: Optional[float] = Field(None, ge=0.0, le=1.0,
                                           description="商城折扣率（NULL=无折扣，仅后台可配）")
    is_active: bool = True
    is_recommended: bool = Field(False, description="是否推荐套餐（用户端金色描边+角标）")
    sort_order: int = 0


class MembershipPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    price_month: Optional[float] = None
    price_year: Optional[float] = None
    max_managed: Optional[int] = None
    ai_outbound_call_count: Optional[int] = None
    emergency_ai_call_count: Optional[int] = None
    max_managed_by: Optional[int] = None
    discount_rate: Optional[float] = None
    is_active: Optional[bool] = None
    is_recommended: Optional[bool] = None
    sort_order: Optional[int] = None


class MembershipPlanResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price_month: Optional[float] = None
    price_year: Optional[float] = None
    max_managed: int
    ai_outbound_call_count: int
    emergency_ai_call_count: int
    max_managed_by: int
    discount_rate: Optional[float] = None
    is_active: bool
    is_recommended: bool = False
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── Free Quota ────────────────


class FreeMemberQuotaUpdate(BaseModel):
    max_managed: Optional[int] = None
    ai_outbound_call_count: Optional[int] = None
    emergency_ai_call_count: Optional[int] = None
    max_managed_by: Optional[int] = None


class FreeMemberQuotaResponse(BaseModel):
    id: int
    max_managed: int
    ai_outbound_call_count: int
    emergency_ai_call_count: int
    max_managed_by: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── User Membership ────────────────


class UserMembershipResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    plan_name: Optional[str] = None
    billing_cycle: str
    start_at: datetime
    expire_at: datetime
    status: str
    discount_rate: Optional[float] = None
    max_managed: Optional[int] = None
    max_managed_by: Optional[int] = None
    ai_outbound_call_count: Optional[int] = None
    emergency_ai_call_count: Optional[int] = None
    auto_renew: bool

    model_config = ConfigDict(from_attributes=True)


class MembershipMeResponse(BaseModel):
    """当前用户的会员状态简要信息（用户端使用）"""
    is_paid_member: bool
    plan_id: Optional[int] = None
    plan_name: Optional[str] = None
    expire_at: Optional[datetime] = None
    max_managed: int = 3
    max_managed_by: int = 3
    ai_outbound_call_count: int = 5
    emergency_ai_call_count: int = 3
    # discount_rate 仅后端透传，用户端不渲染
    discount_rate: Optional[float] = None


class MembershipSubscribeRequest(BaseModel):
    plan_id: int
    billing_cycle: str = "monthly"  # monthly / yearly


# ──────────────── 后台：用户会员卡片 / 调整操作 ────────────────


class UserMembershipCardResponse(BaseModel):
    """后台用户详情 - 会员信息卡片"""
    user_id: int
    plan_id: Optional[int] = None
    plan_name: str = "免费会员"
    is_paid_member: bool = False
    expire_at: Optional[datetime] = None
    days_remaining: Optional[int] = None

    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径变更：家庭守护成员总人数（含本人）
    max_managed_limit: int = 4            # 家庭守护成员总人数上限（含本人）
    max_managed_used: int = 0             # 已建档家庭守护成员数（含本人，包括本人卡）
    max_managed_by_limit: int = 3         # 被守护上限
    max_managed_by_used: int = 0          # 已被守护人数
    ai_outbound_call_limit: int = 5
    ai_outbound_call_used: int = 0
    ai_outbound_call_remaining: int = 5
    emergency_ai_call_limit: int = 3
    emergency_ai_call_used: int = 0
    emergency_ai_call_remaining: int = 3


class UserMembershipAdjustRequest(BaseModel):
    """后台会员调整请求"""
    action: Literal["extend", "downgrade", "reset_quota"]
    days: Optional[int] = Field(None, ge=1, description="延期天数（action=extend 必填）")


# ──────────────── Discount Calculation ────────────────


class DiscountCalcRequest(BaseModel):
    product_id: int
    quantity: int = 1
    user_points: Optional[int] = None


class DiscountOptionItem(BaseModel):
    type: str
    label: str
    discount_amount: float
    final_price: float
    detail: Optional[str] = None
    use_points: Optional[int] = None


class DiscountCalcResponse(BaseModel):
    product_id: int
    quantity: int
    original_price: float
    is_paid_member: bool
    user_points: int
    member_discount_eligible: bool
    points_deductible: bool
    options: list[DiscountOptionItem]
    recommended: str
