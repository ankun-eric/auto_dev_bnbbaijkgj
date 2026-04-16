from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MemberQRCodeResponse(BaseModel):
    token: str
    expires_at: datetime
    user_id: int


class VerifyMemberQRRequest(BaseModel):
    token: str


class VerifyMemberQRResponse(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None
    member_level: int = 0
    points: int = 0


class CheckinRequest(BaseModel):
    token: str
    store_id: int


class CheckinResponse(BaseModel):
    id: int
    user_id: int
    store_id: int
    points_earned: int
    checked_in_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RedeemRequest(BaseModel):
    verification_code: str
    store_id: Optional[int] = None


class RedeemResponse(BaseModel):
    id: int
    order_item_id: int
    redeemed_by_user_id: int
    store_id: Optional[int] = None
    redeemed_at: datetime
    remaining_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class StoreVisitResponse(BaseModel):
    id: int
    user_id: int
    store_id: int
    visited_at: datetime
    consumption_amount: float = 0

    model_config = ConfigDict(from_attributes=True)


class CheckinRecordResponse(BaseModel):
    id: int
    user_id: int
    store_id: int
    staff_user_id: Optional[int] = None
    points_earned: int
    checked_in_at: datetime
    user_nickname: Optional[str] = None
    user_phone: Optional[str] = None
    store_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CheckinConfigRequest(BaseModel):
    points_per_checkin: int = 5
    daily_limit: int = 1
