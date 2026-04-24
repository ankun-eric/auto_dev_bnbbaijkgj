"""商家后台 v1 schemas：机构类别、订单附件、对账单、发票、导出、PC Web 登录/工作台"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────── 机构类别 ────────────────

class MerchantCategoryBase(BaseModel):
    code: str
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None
    allowed_attachment_types: List[str] = Field(default_factory=lambda: ["image", "pdf"])
    attachment_label: Optional[str] = None
    sort: int = 0
    status: str = "active"


class MerchantCategoryCreate(MerchantCategoryBase):
    pass


class MerchantCategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    allowed_attachment_types: Optional[List[str]] = None
    attachment_label: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[str] = None


class MerchantCategoryResponse(MerchantCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 订单附件 ────────────────

class OrderAttachmentResponse(BaseModel):
    id: int
    order_id: int
    order_source: str = "unified"
    store_id: Optional[int] = None
    uploader_user_id: int
    file_type: str
    file_url: str
    file_name: Optional[str] = None
    file_size: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderAttachmentCreateRequest(BaseModel):
    order_id: int
    order_source: str = "unified"
    file_type: str = Field(..., description="image 或 pdf")
    file_url: str
    file_name: Optional[str] = None
    file_size: int = 0
    store_id: Optional[int] = None


# ──────────────── PC Web 登录 ────────────────

class MerchantLoginRequest(BaseModel):
    phone: str
    password: Optional[str] = None
    sms_code: Optional[str] = None


class MerchantLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    phone: str
    nickname: Optional[str] = None
    merchant_role: str
    store_count: int
    stores: List[dict] = Field(default_factory=list)


# ──────────────── 工作台 ────────────────

class MerchantWorkbenchMetrics(BaseModel):
    store_id: Optional[int] = None
    store_name: Optional[str] = None
    today_orders: int = 0
    today_verifications: int = 0
    month_gmv: float = 0
    pending_settlement: float = 0
    pending_attachments: int = 0
    unread_messages: int = 0


# ──────────────── 订单管理 ────────────────

class MerchantOrderItem(BaseModel):
    order_id: int
    order_no: str
    user_display: str
    product_name: str
    created_at: datetime
    appointment_time: Optional[datetime] = None
    store_id: Optional[int] = None
    store_name: Optional[str] = None
    status: str
    amount: float
    attachment_count: int = 0


class MerchantOrderListResponse(BaseModel):
    items: List[MerchantOrderItem]
    total: int
    page: int
    page_size: int


# ──────────────── 核销记录 ────────────────

class MerchantVerificationRecord(BaseModel):
    id: int
    order_no: str
    product_name: str
    user_display: str
    store_name: str
    verifier_name: str
    verified_at: datetime
    amount: float


# ──────────────── 报表分析 ────────────────

class ReportSeriesPoint(BaseModel):
    label: str
    orders: int = 0
    gmv: float = 0
    verifications: int = 0


class ReportAnalysisResponse(BaseModel):
    period: str
    dim: str
    series: List[ReportSeriesPoint]
    total_orders: int
    total_gmv: float
    total_verifications: int
    top_products: List[dict] = Field(default_factory=list)


# ──────────────── 对账单 ────────────────

class SettlementStatementBrief(BaseModel):
    id: int
    statement_no: str
    merchant_profile_id: int
    store_id: Optional[int] = None
    dim: str
    period_start: date
    period_end: date
    order_count: int = 0
    total_amount: float = 0
    settlement_amount: float = 0
    status: str
    confirmed_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SettlementConfirmRequest(BaseModel):
    remark: Optional[str] = None


class SettlementDisputeRequest(BaseModel):
    reason: str


class SettlementGenerateRequest(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    merchant_profile_id: Optional[int] = None


class PaymentProofCreateRequest(BaseModel):
    file_url: str
    file_name: Optional[str] = None
    amount: float = 0
    paid_at: Optional[datetime] = None


# ──────────────── 发票 ────────────────

class InvoiceProfileSchema(BaseModel):
    title: Optional[str] = None
    tax_no: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    register_address: Optional[str] = None
    register_phone: Optional[str] = None
    receive_address: Optional[str] = None
    receive_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 导出任务 ────────────────

class ExportTaskCreateRequest(BaseModel):
    task_type: str = Field(..., description="orders / verifications / settlement / report")
    task_name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    store_id: Optional[int] = None


class ExportTaskResponse(BaseModel):
    id: int
    task_name: str
    task_type: str
    status: str
    file_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 员工 ────────────────

class MerchantStaffResponse(BaseModel):
    user_id: int
    phone: str
    nickname: Optional[str] = None
    member_role: str
    store_ids: List[int] = Field(default_factory=list)
    status: str = "active"


# ──────────────── 商家身份状态 ────────────────

class MerchantStatusResponse(BaseModel):
    is_merchant: bool
    merchant_role: Optional[str] = None
    store_count: int = 0
    category_code: Optional[str] = None
