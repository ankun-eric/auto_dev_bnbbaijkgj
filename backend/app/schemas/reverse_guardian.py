from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class GuardianItem(BaseModel):
    # [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] item_type 区分 active / pending
    item_type: str = "active"  # "active" | "pending"
    management_id: Optional[int] = None
    invitation_id: Optional[int] = None
    invite_code: Optional[str] = None
    user_id: Optional[int] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    guardian_since: Optional[datetime] = None
    permission_scope: str = "全部健康信息"
    last_viewed_at: Optional[datetime] = None
    # pending 项专属
    invite_expires_at: Optional[datetime] = None
    invite_status: Optional[str] = None  # pending/active/expired

    model_config = ConfigDict(from_attributes=True)


class MyGuardiansResponse(BaseModel):
    items: List[GuardianItem]
    total: int
    # [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 增加 active/pending 计数
    active_count: int = 0
    pending_count: int = 0


class GuardianCountResponse(BaseModel):
    # [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 拆双数字：已守护 / 待确认
    count: int  # 兼容旧前端，= active_count
    active_count: Optional[int] = 0
    pending_count: Optional[int] = 0
    total_count: Optional[int] = 0
    # [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 守护我的人上限与会员等级
    max_guardians_for_me: Optional[int] = 0  # Y = 被管理上限
    max_guardians_by_me: Optional[int] = 0   # 我守护的人 Y = 管理上限
    bound_others_count: Optional[int] = 0    # 我守护的人 X（已绑定非本人）
    is_top_level: Optional[bool] = False     # 是否顶级会员
    is_unlimited: Optional[bool] = False     # 是否无上限
    member_level: Optional[str] = "free"     # 会员等级名称


class CancelReverseInviteRequest(BaseModel):
    invitation_id: Optional[int] = None
    invite_code: Optional[str] = None


class CancelReverseInviteResponse(BaseModel):
    invitation_id: int
    status: str
    message: str


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
