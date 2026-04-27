from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class VideoConsultConfigResponse(BaseModel):
    id: int
    enabled: bool = False
    seat_url: Optional[str] = None
    service_start_time: Optional[str] = None
    service_end_time: Optional[str] = None
    max_queue: int = 10
    welcome_message: Optional[str] = None
    wait_message: Optional[str] = None
    timeout_seconds: int = 300
    offline_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VideoConsultConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    seat_url: Optional[str] = None
    service_start_time: Optional[str] = None
    service_end_time: Optional[str] = None
    max_queue: Optional[int] = None
    welcome_message: Optional[str] = None
    wait_message: Optional[str] = None
    timeout_seconds: Optional[int] = None
    offline_message: Optional[str] = None
