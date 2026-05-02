from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


ALLOWED_APPOINTMENT_MODES = {"none", "date", "time_slot", "custom_form"}

# 商品功能优化 v1.0：营销角标（运营后台可多选）
ALLOWED_MARKETING_BADGES = {"limited", "hot", "new", "recommend"}
# 展示优先级：限时 > 热销 > 新品 > 推荐
MARKETING_BADGE_PRIORITY = ["limited", "hot", "new", "recommend"]


def _clean_marketing_badges(value: Optional[list[str]]) -> Optional[list[str]]:
    """校验并去重营销角标列表；不合法值直接抛 ValueError。"""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("marketing_badges 必须是字符串数组")
    result: list[str] = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"marketing_badges 包含非字符串：{item!r}")
        if item not in ALLOWED_MARKETING_BADGES:
            raise ValueError(
                f"marketing_badges 存在非法值：{item}，允许值：{sorted(ALLOWED_MARKETING_BADGES)}"
            )
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
ALLOWED_PURCHASE_APPT_MODES = {
    "purchase_with_appointment",
    "appointment_later",
    # 历史别名兼容
    "must_appoint",
    "appoint_later",
}


class TimeSlotItem(BaseModel):
    """时段项：起止时间 + 容量"""
    start: str  # HH:MM
    end: str  # HH:MM
    capacity: int = 0


def _validate_appointment_mode(
    appointment_mode: Optional[str],
    purchase_appointment_mode: Optional[str],
    advance_days: Optional[int],
    daily_quota: Optional[int],
    time_slots: Optional[list],
    custom_form_id: Optional[int],
    allow_partial: bool = False,
) -> None:
    """预约模式与联动必填字段校验。

    allow_partial=True 时（用于 PUT 部分更新），仅校验"已传入值的合法性"，
    不要求提供所有联动字段；这允许运营从 none 切到 date 时在同一请求里补齐。
    allow_partial=False 时（POST 新建），严格要求联动必填项齐全。
    """
    if appointment_mode is None:
        return
    if appointment_mode not in ALLOWED_APPOINTMENT_MODES:
        raise ValueError(
            f"预约模式不合法：{appointment_mode}，必须为 {sorted(ALLOWED_APPOINTMENT_MODES)}"
        )
    if (
        purchase_appointment_mode is not None
        and purchase_appointment_mode not in ALLOWED_PURCHASE_APPT_MODES
    ):
        raise ValueError(
            f"下单预约方式不合法：{purchase_appointment_mode}"
        )

    if appointment_mode == "none":
        return

    # 需要预约时，购买预约方式必填（严格模式下）
    if not allow_partial and not purchase_appointment_mode:
        raise ValueError("预约模式下必须选择下单预约方式（下单即预约 / 先下单后预约）")

    if appointment_mode == "date":
        if not allow_partial:
            if not advance_days or advance_days <= 0:
                raise ValueError("预约日期模式下，提前可预约天数必填且需大于 0")
            if not daily_quota or daily_quota <= 0:
                raise ValueError("预约日期模式下，单日最大预约人数必填且需大于 0")
    elif appointment_mode == "time_slot":
        if not allow_partial:
            # BUG-PRODUCT-APPT-002：time_slot 模式同样必须配置 advance_days
            if not advance_days or advance_days <= 0:
                raise ValueError("预约时段模式下，提前可预约天数必填且需大于 0")
            if not time_slots or len(time_slots) == 0:
                raise ValueError("预约时段模式下，至少配置 1 个时段")
        if time_slots:
            for idx, slot in enumerate(time_slots):
                start = slot.start if hasattr(slot, "start") else slot.get("start")
                end = slot.end if hasattr(slot, "end") else slot.get("end")
                capacity = slot.capacity if hasattr(slot, "capacity") else slot.get("capacity", 0)
                if not start or not end:
                    raise ValueError(f"第 {idx + 1} 个时段的开始/结束时间必填")
                if capacity is None or int(capacity) <= 0:
                    raise ValueError(f"第 {idx + 1} 个时段的容量必须大于 0")
    elif appointment_mode == "custom_form":
        if not allow_partial and not custom_form_id:
            raise ValueError("自定义表单模式下，必须绑定一张预约表单")


class ProductCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0
    status: str = "active"
    level: int = 1


class ProductCategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None


class ProductCategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int
    status: str
    level: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductCategoryTreeResponse(ProductCategoryResponse):
    children: list["ProductCategoryTreeResponse"] = []


class ProductSkuCreate(BaseModel):
    """商品规格创建/更新项（随商品主表一起提交）"""
    id: Optional[int] = None  # 已有规格的 ID（编辑时传入），新增则为空
    spec_name: str
    sale_price: float
    origin_price: Optional[float] = None
    stock: int = 0
    is_default: bool = False
    status: int = 1  # 1=启用 2=停用
    sort_order: int = 0


class ProductSkuResponse(BaseModel):
    id: int
    product_id: int
    spec_name: str
    sale_price: float
    origin_price: Optional[float] = None
    stock: int
    is_default: bool
    status: int
    sort_order: int
    has_orders: bool = False  # 是否被订单引用（用于前端锁定交互）

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str
    category_id: int
    fulfillment_type: str
    original_price: Optional[float] = None
    sale_price: float
    images: Optional[Any] = None
    video_url: Optional[str] = None
    description: Optional[str] = None
    symptom_tags: Optional[Any] = None
    stock: int = 0
    points_exchangeable: bool = False
    points_price: int = 0
    points_deductible: bool = False
    redeem_count: int = 1
    appointment_mode: str = "none"
    purchase_appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
    # ── 预约联动字段 ──
    advance_days: Optional[int] = None
    daily_quota: Optional[int] = None
    time_slots: Optional[list[TimeSlotItem]] = None
    # BUG-PRODUCT-APPT-002：date / time_slot 共用「是否包含今天」，默认 True
    include_today: bool = True
    faq: Optional[Any] = None
    recommend_weight: int = 0
    status: str = "draft"
    sort_order: int = 0
    payment_timeout_minutes: int = 15
    store_ids: Optional[list[int]] = None
    # ── v2 新字段 ──
    product_code_list: Optional[list[str]] = None
    spec_mode: int = 1  # 1=统一规格 2=多规格
    main_video_url: Optional[str] = None
    selling_point: Optional[str] = None
    description_rich: Optional[str] = None
    skus: Optional[list[ProductSkuCreate]] = None  # 多规格模式下提交
    # ── v1.0 商品功能优化：营销角标 ──
    marketing_badges: Optional[list[str]] = None

    @field_validator("marketing_badges")
    @classmethod
    def _check_badges(cls, v):
        return _clean_marketing_badges(v)

    @model_validator(mode="after")
    def _validate_appointment(self):
        _validate_appointment_mode(
            self.appointment_mode,
            self.purchase_appointment_mode,
            self.advance_days,
            self.daily_quota,
            self.time_slots,
            self.custom_form_id,
        )
        return self


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    fulfillment_type: Optional[str] = None
    original_price: Optional[float] = None
    sale_price: Optional[float] = None
    images: Optional[Any] = None
    video_url: Optional[str] = None
    description: Optional[str] = None
    symptom_tags: Optional[Any] = None
    stock: Optional[int] = None
    points_exchangeable: Optional[bool] = None
    points_price: Optional[int] = None
    points_deductible: Optional[bool] = None
    redeem_count: Optional[int] = None
    appointment_mode: Optional[str] = None
    purchase_appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
    advance_days: Optional[int] = None
    daily_quota: Optional[int] = None
    time_slots: Optional[list[TimeSlotItem]] = None
    # BUG-PRODUCT-APPT-002：date / time_slot 共用「是否包含今天」，PUT 部分更新可不传
    include_today: Optional[bool] = None
    faq: Optional[Any] = None
    recommend_weight: Optional[int] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
    payment_timeout_minutes: Optional[int] = None
    store_ids: Optional[list[int]] = None
    # ── v2 新字段 ──
    product_code_list: Optional[list[str]] = None
    spec_mode: Optional[int] = None
    main_video_url: Optional[str] = None
    selling_point: Optional[str] = None
    description_rich: Optional[str] = None
    skus: Optional[list[ProductSkuCreate]] = None
    # ── v1.0 商品功能优化：营销角标 ──
    marketing_badges: Optional[list[str]] = None

    @field_validator("marketing_badges")
    @classmethod
    def _check_badges(cls, v):
        return _clean_marketing_badges(v)

    @model_validator(mode="after")
    def _validate_appointment(self):
        # 仅在传入 appointment_mode 时校验；否则视作未修改预约项
        if self.appointment_mode is not None:
            _validate_appointment_mode(
                self.appointment_mode,
                self.purchase_appointment_mode,
                self.advance_days,
                self.daily_quota,
                self.time_slots,
                self.custom_form_id,
                allow_partial=True,
            )
        return self


class ProductStoreResponse(BaseModel):
    id: int
    store_id: int
    store_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AvailableStoreItem(BaseModel):
    store_id: int
    store_code: Optional[str] = None
    name: str
    address: Optional[str] = None
    # [2026-05-01 门店地图能力 PRD v1.0] 新增字段
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    distance_km: Optional[float] = None
    is_nearest: bool = False
    static_map_url: Optional[str] = None
    # [2026-05-02 H5 下单流程优化 PRD v1.0]
    slot_capacity: Optional[int] = 10
    business_start: Optional[str] = None
    business_end: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class UserLocationInfo(BaseModel):
    lat: float
    lng: float
    source: str = "gps"


class AvailableStoresData(BaseModel):
    user_location: Optional[UserLocationInfo] = None
    stores: List[AvailableStoreItem]
    sort_by: str  # "distance" 或 "name"


class AvailableStoresResponse(BaseModel):
    code: int = 0
    data: AvailableStoresData


class ProductResponse(BaseModel):
    id: int
    name: str
    category_id: int
    fulfillment_type: str
    original_price: Optional[float] = None
    sale_price: float
    images: Optional[Any] = None
    video_url: Optional[str] = None
    description: Optional[str] = None
    symptom_tags: Optional[Any] = None
    stock: int
    points_exchangeable: bool
    points_price: int
    points_deductible: bool
    redeem_count: int
    appointment_mode: str
    purchase_appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
    advance_days: Optional[int] = None
    daily_quota: Optional[int] = None
    time_slots: Optional[list[TimeSlotItem]] = None
    # BUG-PRODUCT-APPT-002：date / time_slot 共用「是否包含今天」
    include_today: bool = True
    faq: Optional[Any] = None
    recommend_weight: int
    sales_count: int
    status: str
    sort_order: int
    payment_timeout_minutes: int
    # ── v2 新字段 ──
    product_code_list: Optional[list[str]] = None
    spec_mode: int = 1
    main_video_url: Optional[str] = None
    selling_point: Optional[str] = None
    description_rich: Optional[str] = None
    skus: list[ProductSkuResponse] = []
    # ── v1.0 商品功能优化：营销角标 ──
    marketing_badges: list[str] = []
    # ── 多规格价格修复：派生字段 ──
    min_price: Optional[float] = None
    has_multi_spec: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("marketing_badges", mode="before")
    @classmethod
    def _coerce_marketing_badges(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v if isinstance(x, str) and x in ALLOWED_MARKETING_BADGES]
        return []

    @model_validator(mode='after')
    def _compute_min_price(self):
        if self.spec_mode == 2 and self.skus:
            enabled_skus = [s for s in self.skus if getattr(s, 'status', 1) == 1]
            if enabled_skus:
                prices = [s.sale_price for s in enabled_skus if s.sale_price > 0]
                if prices:
                    self.min_price = min(prices)
                    self.sale_price = self.min_price
                    self.has_multi_spec = len(set(prices)) > 1
                else:
                    self.min_price = self.sale_price
            else:
                self.min_price = self.sale_price
        else:
            self.min_price = self.sale_price
        return self


class ProductDetailResponse(ProductResponse):
    stores: list[ProductStoreResponse] = []
    review_count: int = 0
    avg_rating: Optional[float] = None
    category_name: Optional[str] = None


class AppointmentFormCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "active"


class AppointmentFormUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class AppointmentFormResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str = "active"
    field_count: int = 0
    product_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentFormFieldCreate(BaseModel):
    field_type: str
    label: str
    placeholder: Optional[str] = None
    required: bool = False
    options: Optional[Any] = None
    sort_order: int = 0


class AppointmentFormFieldUpdate(BaseModel):
    field_type: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    required: Optional[bool] = None
    options: Optional[Any] = None
    sort_order: Optional[int] = None


class AppointmentFormFieldResponse(BaseModel):
    id: int
    form_id: int
    field_type: str
    label: str
    placeholder: Optional[str] = None
    required: bool
    options: Optional[Any] = None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SymptomTagResponse(BaseModel):
    tag: str
    count: int
