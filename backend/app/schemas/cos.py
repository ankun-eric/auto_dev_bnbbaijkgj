from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CosConfigUpdate(BaseModel):
    secret_id: Optional[str] = None
    secret_key: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    image_prefix: Optional[str] = None
    video_prefix: Optional[str] = None
    file_prefix: Optional[str] = None
    is_active: Optional[bool] = None


class CosConfigResponse(BaseModel):
    id: int
    secret_id: Optional[str] = None
    secret_key_masked: str = ""
    bucket: Optional[str] = None
    region: Optional[str] = None
    image_prefix: str = "images/"
    video_prefix: str = "videos/"
    file_prefix: str = "files/"
    is_active: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CosFileResponse(BaseModel):
    id: int
    file_key: str
    file_url: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    original_name: Optional[str] = None
    module: Optional[str] = None
    ref_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CosUsageResponse(BaseModel):
    total_files: int = 0
    total_size: int = 0
    total_size_mb: float = 0.0
    by_type: dict = {}
