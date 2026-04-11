from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class InvitationCreateRequest(BaseModel):
    member_id: int


class InvitationCreateResponse(BaseModel):
    invite_code: str
    qr_url: str
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationDetailResponse(BaseModel):
    invite_code: str
    status: str
    inviter_nickname: Optional[str] = None
    member_nickname: Optional[str] = None
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationAcceptRequest(BaseModel):
    pass


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
