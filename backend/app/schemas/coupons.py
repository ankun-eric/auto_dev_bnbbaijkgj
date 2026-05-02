from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


VALIDITY_DAYS_OPTIONS = [3, 7, 15, 30, 60, 90, 180, 365]

# 适用范围 / 排除商品上限默认值（最终以 system_configs 配置为准，可后台动态调整）
DEFAULT_COUPON_SCOPE_MAX_PRODUCTS = 100
DEFAULT_COUPON_EXCLUDE_MAX_PRODUCTS = 50

# 优惠券类型说明文案（前端可直接 GET 拉取 → 渲染说明弹窗，便于运营后续在后端文案中心动态维护）
COUPON_TYPE_DESCRIPTIONS: list[dict] = [
    {
        "key": "full_reduction",
        "name": "满减券",
        "icon": "💰",
        "core_rule": "必须满足门槛金额才能使用，达到门槛后直接减去固定金额",
        "key_fields": "使用门槛金额（必填且 > 0）、优惠金额",
        "scenarios": "拉高客单价 / 大促主力券 / 凑单引导",
        "example": "满 200 减 30 → 用户下单满 200 元才能用，结算时直接减 30",
        "note": "",
    },
    {
        "key": "discount",
        "name": "折扣券",
        "icon": "🏷️",
        "core_rule": "按折扣率对订单金额打折；门槛金额可选（=0 表示无门槛）",
        "key_fields": "折扣率（0.01~1，例如 0.8 = 八折）、使用门槛金额",
        "scenarios": "会员折扣 / 品类折扣 / 新人折扣",
        "example": "折扣率 0.7 + 门槛 300 → 满 300 享 7 折",
        "note": "折扣型对客单价较敏感，建议配合门槛金额使用，避免被薅小订单",
    },
    {
        "key": "voucher",
        "name": "代金券",
        "icon": "🎫",
        "core_rule": '相当于"现金抵扣"，可设置门槛或不设门槛（门槛=0 即无门槛）',
        "key_fields": "优惠金额（必填）、使用门槛金额（可选）",
        "scenarios": "拉新激活 / 售后补偿 / 异业合作 / 兑换码批次发放",
        "example": "代金 50 + 门槛 0 → 用户领券后直接抵扣 50 元",
        "note": '与满减券的区别：代金券强调"现金属性"（可无门槛）；满减券强调"凑单门槛"（满 N 才能用）',
    },
    {
        "key": "free_trial",
        "name": "免费试用",
        "icon": "🎁",
        "core_rule": '本质是"整单 0 元/兑换"，凭券免费领取/试用指定商品',
        "key_fields": '建议必须搭配"适用范围 = 指定商品"使用',
        "scenarios": "新品冷启动试用 / 新人首单 0 元 / 服务体验券",
        "example": "免费试用 + 指定商品「头部按摩 30 分钟」",
        "note": "风控建议：必须限发指定商品 + 设置发行总量 + 单人限领，避免被刷",
    },
]


class CouponCreate(BaseModel):
    name: str
    type: str
    condition_amount: float = 0
    discount_value: float = 0
    discount_rate: float = 1.0
    scope: str = "all"
    scope_ids: Optional[Any] = None
    exclude_ids: Optional[list[int]] = None
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
    exclude_ids: Optional[list[int]] = None
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
    exclude_ids: Optional[list[int]] = None
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
