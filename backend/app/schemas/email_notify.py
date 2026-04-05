from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EmailConfigResponse(BaseModel):
    enable_email_notify: bool = False
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    has_smtp_password: bool = False


class EmailConfigUpdate(BaseModel):
    enable_email_notify: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None


class EmailLogResponse(BaseModel):
    id: int
    to_email: str
    subject: str
    status: str
    error_message: Optional[str] = None
    is_test: bool
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class EmailTestRequest(BaseModel):
    to_email: str
    subject: str
    content: Optional[str] = None
