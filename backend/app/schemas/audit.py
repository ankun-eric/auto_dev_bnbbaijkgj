from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditPhoneCreate(BaseModel):
    phone: str
    note: Optional[str] = None
    enabled: bool = True


class AuditPhoneUpdate(BaseModel):
    phone: Optional[str] = None
    note: Optional[str] = None
    enabled: Optional[bool] = None


class AuditPhoneResponse(BaseModel):
    id: int
    phone: str
    note: Optional[str] = None
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditRequestResponse(BaseModel):
    id: int
    biz_type: str
    risk_level: str
    status: str
    summary: Optional[str] = None
    est_amount: float = 0
    est_count: int = 0
    approval_mode: str
    requester_id: Optional[int] = None
    requester_name: Optional[str] = None
    return_reason: Optional[str] = None
    modify_note: Optional[str] = None
    approver_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    payload: Any = None
    history: Any = None
    approvals: Any = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditCodeSendRequest(BaseModel):
    phone: str
    request_id: Optional[int] = None


class AuditCodeVerifyRequest(BaseModel):
    phone: str
    code: str
    request_id: int


class AuditApproveRequest(BaseModel):
    request_id: int
    phone: str
    code: str


class AuditReturnRequest(BaseModel):
    request_id: int
    return_reason: str


class AuditResubmitRequest(BaseModel):
    request_id: int
    modify_note: str
    payload: Optional[Any] = None
