"""卡功能（PRD v1.1 第 1 期）相关 Pydantic Schemas。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────── Admin: 卡定义 CRUD ───────────────


class CardItemRef(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    product_image: Optional[str] = None


class StoreScope(BaseModel):
    """卡的核销门店范围。"""

    type: str = Field(..., description="all | list")
    store_ids: Optional[List[int]] = None

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in ("all", "list"):
            raise ValueError("store_scope.type 必须为 all 或 list")
        return v


class FrequencyLimit(BaseModel):
    """时卡频次限制。"""

    scope: str = Field(..., description="day | week")
    times: int = Field(..., ge=1)

    @field_validator("scope")
    @classmethod
    def _check_scope(cls, v: str) -> str:
        if v not in ("day", "week"):
            raise ValueError("frequency_limit.scope 必须为 day 或 week")
        return v


_VALID_FACE_STYLES = {"ST1", "ST2", "ST3", "ST4"}
_VALID_BG_CODES = {"BG1", "BG2", "BG3", "BG4", "BG5", "BG6", "BG7", "BG8"}


class CardDefinitionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    cover_image: Optional[str] = None
    description: Optional[str] = None
    card_type: str = Field(..., description="times | period")
    scope_type: str = Field("platform", description="merchant | platform")
    owner_merchant_id: Optional[int] = None
    price: Decimal = Field(..., ge=0)
    original_price: Optional[Decimal] = Field(default=None, ge=0)
    total_times: Optional[int] = Field(default=None, ge=1)
    valid_days: int = Field(default=365, ge=1, le=3650, description="默认 365 天")
    frequency_limit: Optional[FrequencyLimit] = None
    store_scope: Optional[StoreScope] = None
    stock: Optional[int] = Field(default=None, ge=0)
    per_user_limit: Optional[int] = Field(default=None, ge=1)
    renew_strategy: str = Field("add_on", description="add_on | new_card")
    item_product_ids: List[int] = Field(default_factory=list)
    # [PRD v1.1] 卡面设置
    face_style: str = Field("ST1", description="ST1~ST4 卡面样式")
    face_bg_code: str = Field("BG1", description="BG1~BG8 卡面背景")
    face_show_flags: int = Field(7, ge=0, le=15, description="4 项显示位 bitmask；默认 7=SH1+SH2+SH3")
    face_layout: str = Field("ON_CARD", description="信息布局，本期固定 ON_CARD")

    @field_validator("face_style")
    @classmethod
    def _check_face_style(cls, v: str) -> str:
        if v not in _VALID_FACE_STYLES:
            raise ValueError("face_style 必须为 ST1~ST4")
        return v

    @field_validator("face_bg_code")
    @classmethod
    def _check_face_bg_code(cls, v: str) -> str:
        if v not in _VALID_BG_CODES:
            raise ValueError("face_bg_code 必须为 BG1~BG8")
        return v

    @field_validator("card_type")
    @classmethod
    def _check_card_type(cls, v: str) -> str:
        if v not in ("times", "period"):
            raise ValueError("card_type 必须为 times 或 period")
        return v

    @field_validator("scope_type")
    @classmethod
    def _check_scope_type(cls, v: str) -> str:
        if v not in ("merchant", "platform"):
            raise ValueError("scope_type 必须为 merchant 或 platform")
        return v

    @field_validator("renew_strategy")
    @classmethod
    def _check_renew(cls, v: str) -> str:
        if v not in ("add_on", "new_card"):
            raise ValueError("renew_strategy 必须为 add_on 或 new_card")
        return v


class CardDefinitionCreate(CardDefinitionBase):
    """创建卡定义。校验：
    - 次卡必须填 total_times
    - 商家专属卡必须填 owner_merchant_id
    """

    def model_post_init(self, __context: Any) -> None:
        if self.card_type == "times" and (self.total_times is None or self.total_times <= 0):
            raise ValueError("次卡（card_type=times）必须填写 total_times（>0）")
        if self.scope_type == "merchant" and not self.owner_merchant_id:
            raise ValueError("商家专属卡（scope_type=merchant）必须填写 owner_merchant_id")


class CardDefinitionUpdate(BaseModel):
    """部分更新。所有字段可空。"""

    name: Optional[str] = None
    cover_image: Optional[str] = None
    description: Optional[str] = None
    card_type: Optional[str] = None
    scope_type: Optional[str] = None
    owner_merchant_id: Optional[int] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    original_price: Optional[Decimal] = Field(default=None, ge=0)
    total_times: Optional[int] = Field(default=None, ge=1)
    valid_days: Optional[int] = Field(default=None, ge=1, le=3650)
    frequency_limit: Optional[FrequencyLimit] = None
    store_scope: Optional[StoreScope] = None
    stock: Optional[int] = Field(default=None, ge=0)
    per_user_limit: Optional[int] = Field(default=None, ge=1)
    renew_strategy: Optional[str] = None
    item_product_ids: Optional[List[int]] = None
    sort_order: Optional[int] = None
    # [PRD v1.1] 卡面设置（更新可选）
    face_style: Optional[str] = None
    face_bg_code: Optional[str] = None
    face_show_flags: Optional[int] = Field(default=None, ge=0, le=15)
    face_layout: Optional[str] = None

    @field_validator("face_style")
    @classmethod
    def _check_face_style_upd(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_FACE_STYLES:
            raise ValueError("face_style 必须为 ST1~ST4")
        return v

    @field_validator("face_bg_code")
    @classmethod
    def _check_face_bg_code_upd(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_BG_CODES:
            raise ValueError("face_bg_code 必须为 BG1~BG8")
        return v


class CardDefinitionResponse(BaseModel):
    id: int
    name: str
    cover_image: Optional[str]
    description: Optional[str]
    card_type: str
    scope_type: str
    owner_merchant_id: Optional[int]
    owner_merchant_name: Optional[str] = None
    price: Decimal
    original_price: Optional[Decimal]
    total_times: Optional[int]
    valid_days: int
    frequency_limit: Optional[Dict[str, Any]]
    store_scope: Optional[Dict[str, Any]]
    stock: Optional[int]
    per_user_limit: Optional[int]
    renew_strategy: str
    status: str
    sales_count: int
    sort_order: int
    items: List[CardItemRef] = Field(default_factory=list)
    # [PRD v1.1] 卡面设置
    face_style: str = "ST1"
    face_bg_code: str = "BG1"
    face_show_flags: int = 7
    face_layout: str = "ON_CARD"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CardListResponse(BaseModel):
    total: int
    items: List[CardDefinitionResponse]


class CardStatusUpdate(BaseModel):
    status: str = Field(..., description="active | inactive")

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in ("active", "inactive"):
            raise ValueError("status 必须为 active 或 inactive")
        return v


# ─────────────── C 端：卡浏览与卡包 ───────────────


class CardPublicResponse(BaseModel):
    """C 端展示用，不包含管理字段。"""

    id: int
    name: str
    cover_image: Optional[str]
    description: Optional[str]
    card_type: str  # times | period
    scope_type: str
    owner_merchant_id: Optional[int]
    price: Decimal
    original_price: Optional[Decimal]
    total_times: Optional[int]
    valid_days: int
    frequency_limit: Optional[Dict[str, Any]]
    store_scope: Optional[Dict[str, Any]]
    items: List[CardItemRef] = Field(default_factory=list)
    sales_count: int
    # [PRD v1.1] 卡面设置（H5 直接复用渲染）
    face_style: str = "ST1"
    face_bg_code: str = "BG1"
    face_show_flags: int = 7
    face_layout: str = "ON_CARD"
    # 计算字段：用户是否已持有可用卡 + 即将到期天数（用于"卡即将到期，可续卡"提示）
    user_has_active_card: bool = False
    nearest_expiry_days: Optional[int] = None

    model_config = {"from_attributes": True}


class CardPublicListResponse(BaseModel):
    total: int
    items: List[CardPublicResponse]


class UserCardResponse(BaseModel):
    """我的-卡包 单张卡。"""

    id: int
    card_definition_id: int
    card_name: str
    cover_image: Optional[str]
    card_type: str
    scope_type: str
    bound_items: List[CardItemRef] = Field(default_factory=list)
    remaining_times: Optional[int]
    total_times: Optional[int]
    frequency_limit: Optional[Dict[str, Any]]
    valid_from: datetime
    valid_to: datetime
    status: str  # active / used_up / expired / refunded
    days_to_expire: Optional[int] = None
    purchase_order_id: Optional[int]
    created_at: datetime
    # [PRD v1.1] 卡面设置（H5 卡包页缩小卡面渲染）
    face_style: str = "ST1"
    face_bg_code: str = "BG1"
    face_show_flags: int = 7
    face_layout: str = "ON_CARD"
    price: Optional[Decimal] = None
    original_price: Optional[Decimal] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class UserCardListResponse(BaseModel):
    total: int
    unused_count: int
    in_use_count: int
    expired_count: int
    items: List[UserCardResponse]


class ProductAvailableCardsResponse(BaseModel):
    """商品详情页：当前商品可用的卡（卡内项目包含本商品）"""

    product_id: int
    items: List[CardPublicResponse]
