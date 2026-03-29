from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SmsConfigCreate(BaseModel):
    secret_id: str
    secret_key: str
    sdk_app_id: str
    sign_name: str
    template_id: str
    app_key: Optional[str] = None


class SmsConfigUpdate(BaseModel):
    secret_id: Optional[str] = None
    secret_key: Optional[str] = None
    sdk_app_id: Optional[str] = None
    sign_name: Optional[str] = None
    template_id: Optional[str] = None
    app_key: Optional[str] = None


class SmsConfigResponse(BaseModel):
    id: int
    secret_id: Optional[str] = None
    sdk_app_id: Optional[str] = None
    sign_name: Optional[str] = None
    template_id: Optional[str] = None
    app_key: Optional[str] = None
    is_active: bool
    has_secret_key: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class SmsLogResponse(BaseModel):
    id: int
    phone: str
    code: Optional[str] = None
    template_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    is_test: bool
    operator_id: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class SmsTestRequest(BaseModel):
    phone: str
    template_id: Optional[str] = None
