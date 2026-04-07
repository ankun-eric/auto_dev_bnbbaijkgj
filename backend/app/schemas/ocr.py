from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def _mask_config_json(config: dict | None) -> dict | None:
    if not config:
        return config
    masked = {}
    secret_keywords = ("key", "secret", "token", "password", "credential")
    for k, v in config.items():
        if isinstance(v, str) and any(kw in k.lower() for kw in secret_keywords):
            masked[k] = _mask_secret(v)
        else:
            masked[k] = v
    return masked


# ──────────────── Provider Config ────────────────


class OcrProviderConfigResponse(BaseModel):
    id: int
    provider_name: str
    display_name: str
    config_json: Optional[Dict[str, Any]] = None
    is_enabled: bool
    is_preferred: bool
    status_label: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("config_json", mode="before")
    @classmethod
    def mask_config(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return _mask_config_json(v)
        return v

    @field_validator("status_label", mode="before")
    @classmethod
    def compute_status_label(cls, v: Any, info: Any) -> str:
        return v or ""


class OcrProviderConfigUpdate(BaseModel):
    config_json: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None


# ──────────────── Scene Template ────────────────


class OcrSceneTemplateCreate(BaseModel):
    scene_name: str
    ai_model_id: Optional[int] = None
    ocr_provider: Optional[str] = None


class OcrSceneTemplateUpdate(BaseModel):
    scene_name: Optional[str] = None
    ai_model_id: Optional[int] = None
    ocr_provider: Optional[str] = None


class OcrSceneTemplateResponse(BaseModel):
    id: int
    scene_name: str
    ai_model_id: Optional[int] = None
    ocr_provider: Optional[str] = None
    is_preset: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── Call Record ────────────────


class OcrCallRecordResponse(BaseModel):
    id: int
    scene_name: Optional[str] = None
    provider_name: str
    status: str
    original_image_url: Optional[str] = None
    ocr_raw_text: Optional[str] = None
    ai_structured_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OcrCallRecordListResponse(BaseModel):
    items: List[OcrCallRecordResponse]
    total: int
    page: int
    page_size: int


# ──────────────── Statistics ────────────────


class OcrProviderStatItem(BaseModel):
    provider_name: str
    total_calls: int
    success_calls: int
    fail_calls: int
    success_rate: float


class OcrStatisticsResponse(BaseModel):
    period: str
    providers: List[OcrProviderStatItem]
    total_calls: int
    total_success: int


# ──────────────── Upload Config ────────────────


class OcrUploadConfigResponse(BaseModel):
    id: int
    max_batch_count: int
    max_file_size_mb: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OcrUploadConfigUpdate(BaseModel):
    max_batch_count: Optional[int] = None
    max_file_size_mb: Optional[int] = None


# ──────────────── Test ────────────────


class OcrTestResponse(BaseModel):
    success: bool
    provider_name: str
    ocr_text: Optional[str] = None
    error: Optional[str] = None


class OcrTestFullResponse(BaseModel):
    success: bool
    provider_name: str
    ocr_text: Optional[str] = None
    ai_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ──────────────── Business Recognize ────────────────


class OcrRecognizeResponse(BaseModel):
    success: bool
    provider_name: Optional[str] = None
    ocr_text: Optional[str] = None
    ai_result: Optional[Dict[str, Any]] = None
    record_id: Optional[int] = None
    session_id: Optional[int] = None
    error: Optional[str] = None


class OcrBatchRecognizeResponse(BaseModel):
    results: List[OcrRecognizeResponse]
    total: int
    success_count: int
    fail_count: int
