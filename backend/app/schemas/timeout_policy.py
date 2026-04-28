from typing import Optional

from pydantic import BaseModel


class TimeoutPolicyResponse(BaseModel):
    urge_minutes: int = 30
    timeout_minutes: int = 60
    timeout_action: str = "auto_cancel"
    reminder_advance_hours: int = 24


class TimeoutPolicyUpdate(BaseModel):
    urge_minutes: Optional[int] = None
    timeout_minutes: Optional[int] = None
    timeout_action: Optional[str] = None
    reminder_advance_hours: Optional[int] = None
