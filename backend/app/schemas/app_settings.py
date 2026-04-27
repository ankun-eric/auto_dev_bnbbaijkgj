from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AppSettingResponse(BaseModel):
    id: int
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AppSettingUpdate(BaseModel):
    value: str
