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
    status: str
    member_role: str
    module_codes: List[str] = Field(default_factory=list)


class MerchantStoreCreate(BaseModel):
    store_name: str
    store_code: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    status: str = "active"


class MerchantStoreUpdate(BaseModel):
    store_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None


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
    store_permissions: List[MerchantStorePermissionInput] = Field(default_factory=list)
    status: str = "active"


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
    stores: List[MerchantStoreResponse] = Field(default_factory=list)
    created_at: datetime


class MerchantDashboardResponse(BaseModel):
    selected_store_id: int
    selected_store_name: str
    today_count: int = 0
    today_amount: float = 0


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
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
