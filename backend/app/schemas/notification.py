from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: Optional[str] = None
    type: str
    is_read: bool
    extra_data: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
