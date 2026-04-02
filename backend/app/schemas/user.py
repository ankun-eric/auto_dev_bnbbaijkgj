from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.merchant import MerchantProfileResponse, SessionContextResponse


class RegisterSettingsResponse(BaseModel):
    """Normalized register settings (invalid stored enums fall back to defaults at read time)."""

    enable_self_registration: bool
    wechat_register_mode: str
    register_page_layout: str
    show_profile_completion_prompt: bool
    member_card_no_rule: str


class UserCreate(BaseModel):
    phone: str
    password: str
    nickname: Optional[str] = None


class UserLogin(BaseModel):
    phone: str
    password: str


class SMSCodeRequest(BaseModel):
    phone: str
    type: str = "login"


class SMSLoginRequest(BaseModel):
    phone: str
    code: str


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    member_card_no: Optional[str] = None
    member_level: int
    points: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    is_new_user: bool = False
    needs_profile_completion: bool = False
    session_context: Optional[SessionContextResponse] = None
    merchant_profile: Optional[MerchantProfileResponse] = None


class FamilyMemberCreate(BaseModel):
    member_user_id: Optional[int] = None
    relationship_type: str
    nickname: Optional[str] = None


class FamilyMemberResponse(BaseModel):
    id: int
    user_id: int
    member_user_id: Optional[int] = None
    relationship_type: str
    nickname: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
