from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


VALIDITY_DAYS_OPTIONS = [3, 7, 15, 30, 60, 90, 180, 365]


class CouponCreate(BaseModel):
    name: str
    type: str
    condition_amount: float = 0
    discount_value: float = 0
    discount_rate: float = 1.0
    scope: str = "all"
    scope_ids: Optional[Any] = None
    total_count: int = 0
    validity_days: int = 30
    status: str = "active"
    points_exchange_limit: Optional[int] = None  # V2.1 预留


class CouponUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    condition_amount: Optional[float] = None
    discount_value: Optional[float] = None
    discount_rate: Optional[float] = None
    scope: Optional[str] = None
    scope_ids: Optional[Any] = None
    total_count: Optional[int] = None
    validity_days: Optional[int] = None
    status: Optional[str] = None
    points_exchange_limit: Optional[int] = None


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
    validity_days: int
    status: str
    is_offline: bool = False
    offline_reason: Optional[str] = None
    offline_at: Optional[datetime] = None
    points_exchange_limit: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── V2.1 下架请求 ───

OFFLINE_REASON_PRESETS = ["活动结束", "配置错误", "库存调整", "业务调整", "其他"]


class CouponOfflineRequest(BaseModel):
    reason_type: str  # 必填，预设之一
    reason_detail: Optional[str] = None  # 仅当 reason_type='其他' 时必填，最少 5 字


# ─── V2.1 兑换码作废请求 ───


class CodeBatchVoidRequest(BaseModel):
    batch_no_confirm: str  # 必填，必须与 batch.batch_no 完全一致
    reason: str


class CodeVoidRequest(BaseModel):
    reason: str


class UserCouponResponse(BaseModel):
    id: int
    user_id: int
    coupon_id: int
    status: str
    used_at: Optional[datetime] = None
    order_id: Optional[int] = None
    expire_at: Optional[datetime] = None
    source: Optional[str] = None
    created_at: datetime
    coupon: Optional[CouponResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CouponClaimRequest(BaseModel):
    coupon_id: int


class CouponDistributeRequest(BaseModel):
    user_ids: list[int]


# ─── 4 种发放方式 ───


class DirectGrantRequest(BaseModel):
    """B 定向发放：手动选用户/手机号"""
    coupon_id: int
    user_ids: Optional[list[int]] = None
    phones: Optional[list[str]] = None
    # 标签筛选条件（用户等级/注册时长/消费行为）
    filter_tags: Optional[dict] = None
    note: Optional[str] = None


class NewUserCouponRuleRequest(BaseModel):
    """D 新人券：注册自动发"""
    coupon_id: int
    enabled: bool = True


class RedeemCodeBatchCreate(BaseModel):
    """F 兑换码批次创建"""
    coupon_id: int
    code_type: str = "universal"  # universal / unique
    name: Optional[str] = None
    total_count: Optional[int] = 0
    universal_code: Optional[str] = None
    per_user_limit: int = 1
    partner_id: Optional[int] = None
    # V2.1：一码通用必填，一次性唯一码自动 = total_count
    claim_limit: Optional[int] = None
    expire_at: Optional[datetime] = None


class RedeemCodeRedeemRequest(BaseModel):
    code: str


# ─── 发放记录 ───


class CouponGrantResponse(BaseModel):
    id: int
    coupon_id: int
    user_id: Optional[int] = None
    user_phone: Optional[str] = None
    method: str
    status: str
    granted_at: datetime
    used_at: Optional[datetime] = None
    order_no: Optional[str] = None
    operator_name: Optional[str] = None
    redeem_code: Optional[str] = None
    recall_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GrantRecallRequest(BaseModel):
    grant_ids: list[int]
    reason: str


# ─── 第三方合作方 ───


class PartnerCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    mode: str = "api"
    notes: Optional[str] = None


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class PartnerResponse(BaseModel):
    id: int
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    mode: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
