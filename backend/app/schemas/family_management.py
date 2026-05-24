from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class InvitationCreateRequest(BaseModel):
    member_id: Optional[int] = None
    nickname: Optional[str] = None
    relationship_type: Optional[str] = None
    relation_type_id: Optional[int] = None
    relation_type: Optional[str] = None


class InvitationCreateResponse(BaseModel):
    invite_code: str
    qr_url: str
    qr_content_url: Optional[str] = None
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MergePreviewField(BaseModel):
    """[PRD-FAMILY-AUTH-MP-V1] 健康档案合并预览字段。"""

    key: str
    label: str
    acceptor_value: Optional[Any] = None
    inviter_value: Optional[Any] = None
    will_merge: bool = False


class InvitationDetailResponse(BaseModel):
    invite_code: str
    status: str
    inviter_user_id: Optional[int] = None
    inviter_nickname: Optional[str] = None
    inviter_avatar: Optional[str] = None
    inviter_phone: Optional[str] = None
    inviter_real_name: Optional[str] = None
    member_id: Optional[int] = None
    member_nickname: Optional[str] = None
    relationship_type: Optional[str] = None
    relation_type: Optional[str] = None
    invite_type: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    # [PRD-FAMILY-AUTH-MP-V1] 当前已登录用户视角下的预判信息
    is_self_invite: bool = False
    current_managed_by_count: int = 0
    max_managed_by_count: int = 3
    reached_managed_by_limit: bool = False
    invalid_reason: Optional[str] = None  # expired/used/cancelled/self/limit/None
    merge_preview: List[MergePreviewField] = []

    model_config = ConfigDict(from_attributes=True)


class InvitationAcceptRequest(BaseModel):
    """[PRD-FAMILY-AUTH-MP-V1] 接受邀请请求，可选 merge_fields 指定需要合并的字段 key 列表。

    - 缺省（None）：保持兼容旧行为，所有可合并字段均执行合并
    - 空列表 []：表示用户取消所有合并，保留原值
    - 字段 key 列表：仅合并这些 key 的字段
    """

    merge_fields: Optional[List[str]] = None


class FamilyManagementResponse(BaseModel):
    id: int
    manager_user_id: int
    manager_nickname: Optional[str] = None
    managed_user_id: int
    managed_user_nickname: Optional[str] = None
    managed_member_id: Optional[int] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManagedByResponse(BaseModel):
    id: int
    manager_user_id: int
    manager_nickname: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationLogResponse(BaseModel):
    id: int
    operator_nickname: Optional[str] = None
    operation_type: str
    operation_detail: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
