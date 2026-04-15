from datetime import date, datetime
from typing import List, Optional

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
    referrer_no: Optional[str] = None


class UserLogin(BaseModel):
    phone: str
    password: str


class SMSCodeRequest(BaseModel):
    phone: str
    type: str = "login"


class SMSLoginRequest(BaseModel):
    phone: str
    code: str
    referrer_no: Optional[str] = None


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
    user_no: Optional[str] = None
    referrer_no: Optional[str] = None
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


class RelationTypeResponse(BaseModel):
    id: int
    name: str
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class FamilyMemberCreate(BaseModel):
    member_user_id: Optional[int] = None
    relationship_type: str
    name: Optional[str] = None
    nickname: Optional[str] = None
    relation_type_id: Optional[int] = None
    birthday: Optional[date] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    medical_histories: List[str] = []
    allergies: List[str] = []


class FamilyMemberUpdate(BaseModel):
    relationship_type: Optional[str] = None
    nickname: Optional[str] = None
    relation_type_id: Optional[int] = None
    birthday: Optional[date] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    medical_histories: Optional[List[str]] = None
    allergies: Optional[List[str]] = None


class FamilyMemberResponse(BaseModel):
    id: int
    user_id: int
    member_user_id: Optional[int] = None
    relationship_type: str
    nickname: Optional[str] = None
    is_self: bool = False
    relation_type_id: Optional[int] = None
    relation_type_name: Optional[str] = None
    birthday: Optional[date] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    medical_histories: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────── 推荐人 & 分享链接 ────────────


class ShareLinkResponse(BaseModel):
    share_link: str
    user_no: str


class LandingPageResponse(BaseModel):
    brand_name: str
    tagline: str
    features: List[str]


class UpdateReferrerRequest(BaseModel):
    referrer_no: str


class ReferralRankingItem(BaseModel):
    user_no: str
    nickname: Optional[str] = None
    phone: Optional[str] = None
    referral_count: int


class ReferralStatsResponse(BaseModel):
    total_referrals: int
    today_referrals: int
    month_referrals: int
    ranking: List[ReferralRankingItem]
    total: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
