from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CosConfigUpdate(BaseModel):
    secret_id: Optional[str] = None
    secret_key: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    image_prefix: Optional[str] = None
    video_prefix: Optional[str] = None
    file_prefix: Optional[str] = None
    is_active: Optional[bool] = None
    cdn_domain: Optional[str] = None
    cdn_protocol: Optional[str] = None

    @field_validator("image_prefix", "video_prefix", "file_prefix", mode="before")
    @classmethod
    def prefix_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            raise ValueError("分类前缀不允许为空字符串")
        return v


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
    cdn_domain: Optional[str] = None
    cdn_protocol: str = "https"
    test_passed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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


# ──────────────── Upload Limits ────────────────


class CosUploadLimitResponse(BaseModel):
    module: str
    module_name: Optional[str] = None
    max_size_mb: int = 50

    model_config = ConfigDict(from_attributes=True)


class CosUploadLimitUpdate(BaseModel):
    module: str
    max_size_mb: int = Field(..., ge=1, le=1024)


class CosUploadLimitBatchUpdate(BaseModel):
    items: List[CosUploadLimitUpdate]


# ──────────────── Migration ────────────────


class CosMigrationGroupItem(BaseModel):
    module: str
    module_name: str
    file_count: int
    total_size: int
    total_size_display: str


class CosMigrationScanResponse(BaseModel):
    groups: List[CosMigrationGroupItem]
    total_files: int
    total_size: int
    total_size_display: str


class CosMigrationStartRequest(BaseModel):
    modules: List[str]


class CosMigrationFailedItem(BaseModel):
    original_url: str
    error_message: Optional[str] = None


class CosMigrationTaskResponse(BaseModel):
    task_id: int
    status: str
    total_files: int
    migrated_count: int
    failed_count: int
    skipped_count: int
    progress_percent: float
    current_file: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    failed_items: List[CosMigrationFailedItem] = []


class CosMigrationStartResponse(BaseModel):
    task_id: int
    status: str
    total_files: int
    message: str
