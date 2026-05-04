from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionContextResponse(BaseModel):
    identity_codes: List[str] = Field(default_factory=list)
    can_access_user: bool = False
    can_access_merchant: bool = False
    is_dual_identity: bool = False
    default_entry: str = "user"
    merchant_identity_type: Optional[str] = None
    show_role_switch: bool = False
    merchant_store_count: int = 0


class MerchantProfileResponse(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MerchantProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class MerchantStoreResponse(BaseModel):
    id: int
    store_name: str
    store_code: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    # [2026-05-01 门店地图能力 PRD v1.0] 经纬度（GCJ-02）
    lat: Optional[float] = None
    lng: Optional[float] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    # 拆分的省/市/区（来自地图选点逆地理编码或 admin 手填）
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    status: str
    member_role: str
    module_codes: List[str] = Field(default_factory=list)
    # [2026-04-24] 门店类别字段
    category_id: Optional[int] = None
    category_code: Optional[str] = None
    category_name: Optional[str] = None
    # [2026-05-02 H5 下单流程优化 PRD v1.0]
    slot_capacity: Optional[int] = 10
    business_start: Optional[str] = None
    business_end: Optional[str] = None
    # [2026-05-03 营业时间/营业范围保存 Bug 修复] 经营范围（商品分类 ID 列表）
    business_scope: Optional[List[int]] = None


class MerchantStoreCreate(BaseModel):
    store_name: str
    # [2026-04-29] store_code 改为后端自动生成，前端无需传入
    store_code: Optional[str] = None
    # [2026-04-24] 新建门店必填「所属类别」
    category_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    # [2026-05-01 门店地图能力 PRD v1.0] 经纬度（新建必填）
    lat: Optional[float] = None
    lng: Optional[float] = None
    longitude: Optional[float] = None  # 兼容字段，等价 lng
    latitude: Optional[float] = None   # 兼容字段，等价 lat
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    status: str = "active"
    # [2026-05-02 H5 下单流程优化 PRD v1.0]
    slot_capacity: Optional[int] = 10
    business_start: Optional[str] = None
    business_end: Optional[str] = None
    # [2026-05-03 营业时间/营业范围保存 Bug 修复] 经营范围一并入主表单保存
    business_scope: Optional[List[int]] = None


class MerchantStoreUpdate(BaseModel):
    store_name: Optional[str] = None
    # [2026-04-24] 允许修改门店类别
    category_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    # [2026-05-01 门店地图能力 PRD v1.0] 经纬度（编辑老门店可空）
    lat: Optional[float] = None
    lng: Optional[float] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    status: Optional[str] = None
    # [2026-05-02 H5 下单流程优化 PRD v1.0]
    slot_capacity: Optional[int] = None
    business_start: Optional[str] = None
    business_end: Optional[str] = None
    # [2026-05-03 营业时间/营业范围保存 Bug 修复] 经营范围一并入主表单保存
    business_scope: Optional[List[int]] = None


class MerchantStorePermissionInput(BaseModel):
    store_id: int
    module_codes: List[str] = Field(default_factory=list)


class MerchantAccountUpsert(BaseModel):
    phone: str
    password: Optional[str] = None
    user_nickname: Optional[str] = None
    user_avatar: Optional[str] = None
    enable_user_identity: bool = False
    merchant_identity_type: str
    # [2026-04-24] 角色模板 code（boss/manager/finance/clerk）
    role_code: Optional[str] = None
    merchant_nickname: Optional[str] = None
    merchant_avatar: Optional[str] = None
    status: str = "active"
    store_ids: List[int] = Field(default_factory=list)
    store_permissions: List[MerchantStorePermissionInput] = Field(default_factory=list)


class MerchantAccountImportItem(BaseModel):
    phone: str
    password: Optional[str] = None
    user_nickname: Optional[str] = None
    enable_user_identity: bool = False
    merchant_nickname: Optional[str] = None
    merchant_identity_type: str = "staff"
    role_code: Optional[str] = None
    store_permissions: List[MerchantStorePermissionInput] = Field(default_factory=list)
    status: str = "active"


class MerchantRoleTemplateResponse(BaseModel):
    code: str
    name: str
    default_modules: List[str] = Field(default_factory=list)
    is_system: bool = True
    sort_order: int = 0


class MerchantStaffPermissionUpdate(BaseModel):
    """店长通过商家端修改下属权限"""
    module_codes: List[str] = Field(default_factory=list)


class MerchantStaffStatusUpdate(BaseModel):
    status: str  # active / disabled


class MerchantAccountImportRequest(BaseModel):
    items: List[MerchantAccountImportItem] = Field(default_factory=list)


class MerchantAccountSummaryResponse(BaseModel):
    id: int
    phone: str
    status: str
    user_nickname: Optional[str] = None
    merchant_nickname: Optional[str] = None
    identity_codes: List[str] = Field(default_factory=list)
    merchant_identity_type: Optional[str] = None
    # [2026-04-24] 角色
    role_code: Optional[str] = None
    role_name: Optional[str] = None
    stores: List[MerchantStoreResponse] = Field(default_factory=list)
    created_at: datetime
    # [2026-04-26] 该老板下挂的非老板员工数量（用于"员工列表 (N)"按钮徽标）
    staff_count: int = 0


class MerchantStaffItemResponse(BaseModel):
    """[2026-04-26] 商家"员工列表"抽屉单条数据"""
    id: int
    phone: str
    name: Optional[str] = None
    role_code: Optional[str] = None
    role_name: Optional[str] = None
    status: str
    status_text: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    store_names: List[str] = Field(default_factory=list)


class MerchantStaffListResponse(BaseModel):
    items: List[MerchantStaffItemResponse] = Field(default_factory=list)
    total: int = 0
    merchant_name: Optional[str] = None


class MerchantDashboardResponse(BaseModel):
    selected_store_id: int
    selected_store_name: str
    today_count: int = 0
    today_amount: float = 0
    today_orders: int = 0
    today_verifications: int = 0
    pending_verify: int = 0
    recent_orders: List[dict] = Field(default_factory=list)


class MerchantVerifyRequest(BaseModel):
    store_id: int
    code: str


class MerchantVerifyOrderResponse(BaseModel):
    id: int
    order_no: str
    service_name: str
    user_name: str
    amount: float
    create_time: datetime
    status: str
    verification_code: Optional[str] = None


class MerchantVerificationRecordResponse(BaseModel):
    id: int
    order_no: str
    service_name: str
    user_name: str
    amount: float
    verify_time: datetime
    store_id: int
    store_name: str


class MerchantNotificationResponse(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    notification_type: Optional[str] = "system"
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────── 预约日历 ────────────


class CalendarDaySummary(BaseModel):
    date: str
    count: int = 0
    morning_count: int = 0
    afternoon_count: int = 0
    evening_count: int = 0
    heat_level_morning: str = "low"
    heat_level_afternoon: str = "low"
    heat_level_evening: str = "low"


class CalendarMonthlyResponse(BaseModel):
    days: List[CalendarDaySummary] = Field(default_factory=list)


class DailyAppointmentItem(BaseModel):
    order_id: int
    order_item_id: int
    time_slot: Optional[str] = None
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    status: Optional[str] = None


class DailyAppointmentResponse(BaseModel):
    date: str
    items: List[DailyAppointmentItem] = Field(default_factory=list)


# ──────────── 预约日历当日订单弹窗（PRD「当日订单弹窗」v1.0） ────────────


class DailyOrderItem(BaseModel):
    """当日订单弹窗的单条订单（一条订单项）。

    状态字段统一合并为 5 个枚举：
    - pending: 待核销（已支付但未核销）
    - verified: 已核销
    - cancelled: 已取消
    - refunded: 已退款
    - other: 其它（兜底，正常不出现）
    """
    order_id: int
    order_item_id: int
    order_no: Optional[str] = None
    time_slot: Optional[str] = Field(default=None, description="预约时段如 14:00-15:00 或 14:00")
    appointment_time: Optional[datetime] = None
    customer_nickname: Optional[str] = Field(default=None, description="客户昵称（脱敏，如 张**）")
    customer_phone: Optional[str] = Field(default=None, description="客户手机号（11 位完整，仅商家可见）")
    service_name: Optional[str] = None
    service_location: Optional[str] = Field(default=None, description="服务地点：门店地址或上门地址快照")
    status: str = Field(description="合并后的状态：pending/verified/cancelled/refunded/other")
    remark: Optional[str] = None
    verify_time: Optional[datetime] = Field(default=None, description="核销时间（仅 status=verified 下发）")
    verify_code: Optional[str] = Field(default=None, description="核销码（仅 status=verified 下发；未核销绝不下发）")
    cancel_time: Optional[datetime] = Field(default=None, description="取消时间（仅 status=cancelled 时填充）")
    cancel_reason: Optional[str] = None
    refund_time: Optional[datetime] = Field(default=None, description="退款时间（仅 status=refunded 时填充）")
    refund_reason: Optional[str] = None


class DailyOrdersByStatus(BaseModel):
    pending: int = 0
    verified: int = 0
    cancelled: int = 0
    refunded: int = 0


class DailyOrdersResponse(BaseModel):
    """GET /api/merchant/calendar/daily-orders 响应。"""
    date: str
    total: int
    by_status: DailyOrdersByStatus = Field(default_factory=DailyOrdersByStatus)
    orders: List[DailyOrderItem] = Field(default_factory=list)


# ──────────── 订单操作 ────────────


class OrderConfirmResponse(BaseModel):
    success: bool
    message: str


class AppointmentTimeAdjustRequest(BaseModel):
    new_date: str
    new_time_slot: Optional[str] = None


class OrderNoteCreate(BaseModel):
    content: str


class OrderNoteResponse(BaseModel):
    id: int
    content: str
    staff_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────── 公众号绑定 ────────────


class WechatBindQrcodeResponse(BaseModel):
    qrcode_url: str
    ticket: str


# ──────────── 预约日历驾驶舱 PRD v1.0 ────────────


class CalendarKpiResponse(BaseModel):
    today_count: int
    week_count: int
    month_count: int


class CalendarCellInfo(BaseModel):
    date: str  # YYYY-MM-DD
    booking_count: int = 0  # 预约（待核销+已核销）
    verified_count: int = 0  # 已核
    occupied_rate: int = 0  # 占用百分比 0-100，向下取整
    revenue: float = 0  # 当日订单实收（已退款不计）
    cancelled_count: int = 0  # 取消数（tooltip 用）


class CalendarCellsResponse(BaseModel):
    cells: List[CalendarCellInfo] = Field(default_factory=list)


class CalendarItemCard(BaseModel):
    order_id: int
    order_item_id: int
    appointment_time: Optional[datetime] = None
    time_slot: Optional[str] = None
    customer_nickname: str = "匿名用户"  # 脱敏
    product_name: Optional[str] = None
    product_id: Optional[int] = None
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None
    status: str  # pending/verified/cancelled/refunded/other
    amount: float = 0
    source: Optional[str] = None  # miniprogram/h5/store/phone/admin


class CalendarItemsResponse(BaseModel):
    items: List[CalendarItemCard] = Field(default_factory=list)
    group_by: str = "service"


class CalendarListItem(BaseModel):
    order_id: int
    order_item_id: int
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    customer_nickname: str = "匿名用户"
    customer_phone: Optional[str] = None
    product_name: Optional[str] = None
    staff_name: Optional[str] = None
    status: str
    amount: float = 0
    source: Optional[str] = None


class CalendarListResponse(BaseModel):
    items: List[CalendarListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# ──────────── 我的视图 ────────────


class MyViewCreate(BaseModel):
    name: str = Field(..., max_length=40)
    view_type: str = Field("month", description="month/week/day/resource/list")
    filter_payload: Optional[dict] = None
    is_default: bool = False


class MyViewUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=40)
    view_type: Optional[str] = None
    filter_payload: Optional[dict] = None
    is_default: Optional[bool] = None


class MyViewResponse(BaseModel):
    id: int
    name: str
    view_type: str
    filter_payload: Optional[dict] = None
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyViewListResponse(BaseModel):
    items: List[MyViewResponse] = Field(default_factory=list)


# ──────────── 改约 ────────────


class RescheduleRequest(BaseModel):
    new_appointment_time: Optional[datetime] = None
    new_product_id: Optional[int] = None
    new_staff_id: Optional[int] = None
    notify_customer: bool = True


class RescheduleResponse(BaseModel):
    success: bool
    order_item_id: int
    appointment_time: Optional[datetime] = None
    product_id: Optional[int] = None
    staff_id: Optional[int] = None
    notify_result: Optional[str] = None  # success / fail / no_subscribe / skipped


# ──────────── 通知 ────────────


class NotifyRequest(BaseModel):
    scene: str = Field(
        "contact_customer",
        description="contact_customer / cancelled / before_1d / before_1h / booked / rescheduled",
    )


class NotifyResponse(BaseModel):
    result: str  # success / fail / no_subscribe
    template_id: Optional[str] = None
    log_id: Optional[int] = None
