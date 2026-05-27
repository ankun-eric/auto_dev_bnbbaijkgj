from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class GuardianItem(BaseModel):
    management_id: int
    user_id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    guardian_since: Optional[datetime] = None
    permission_scope: str = "全部健康信息"
    last_viewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MyGuardiansResponse(BaseModel):
    items: List[GuardianItem]
    total: int


class GuardianCountResponse(BaseModel):
    # [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 拆双数字：已守护 / 待确认
    count: int  # 兼容旧前端，= active_count
    active_count: Optional[int] = 0
    pending_count: Optional[int] = 0
    total_count: Optional[int] = 0


class RemoveGuardianRequest(BaseModel):
    management_id: int


class RemoveGuardianResponse(BaseModel):
    message: str


class ReverseInviteCreateResponse(BaseModel):
    invite_code: str
    qr_url: str
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReverseInviteDetailResponse(BaseModel):
    invite_code: str
    status: str
    invitee_user_id: int
    invitee_nickname: Optional[str] = None
    invitee_avatar: Optional[str] = None
    inviter_real_name: Optional[str] = None
    relation_type: Optional[str] = None
    max_uses: int
    used_count: int
    expires_at: datetime
    created_at: datetime
    check_result: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AcceptReverseInviteResponse(BaseModel):
    message: str
    management_id: int
