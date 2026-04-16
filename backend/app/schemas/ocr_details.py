from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class CheckupReportDetailResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_phone: Optional[str] = None
    user_nickname: Optional[str] = None
    report_type: Optional[str] = None
    abnormal_count: int = 0
    summary: Optional[str] = None
    status: Optional[str] = None
    provider_name: str
    original_image_url: Optional[str] = None
    ocr_raw_text: Optional[str] = None
    ai_structured_result: Optional[Dict[str, Any]] = None
    abnormal_indicators: Optional[Any] = None
    ocr_call_record_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CheckupReportDetailListResponse(BaseModel):
    items: List[CheckupReportDetailResponse]
    total: int
    page: int
    page_size: int


class CheckupReportStatisticsResponse(BaseModel):
    total: int
    today_count: int
    abnormal_count: int
    month_count: int


class DrugIdentifyDetailResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_phone: Optional[str] = None
    user_nickname: Optional[str] = None
    drug_name: Optional[str] = None
    drug_category: Optional[str] = None
    dosage: Optional[str] = None
    precautions: Optional[str] = None
    provider_name: str
    original_image_url: Optional[str] = None
    ocr_raw_text: Optional[str] = None
    ai_structured_result: Optional[Dict[str, Any]] = None
    ocr_call_record_id: Optional[int] = None
    session_id: Optional[int] = None
    family_member_id: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DrugIdentifyDetailListResponse(BaseModel):
    items: List[DrugIdentifyDetailResponse]
    total: int
    page: int
    page_size: int


class DrugIdentifyStatisticsResponse(BaseModel):
    total: int
    today_count: int
    drug_types_count: int
    month_count: int


class FamilyMemberBrief(BaseModel):
    id: int
    nickname: Optional[str] = None
    relationship_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DrugIdentifyHistoryItem(BaseModel):
    id: int
    image_url: Optional[str] = None
    drug_name: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    session_id: Optional[int] = None
    family_member_id: Optional[int] = None
    family_member: Optional[FamilyMemberBrief] = None

    model_config = ConfigDict(from_attributes=True)


class DrugIdentifyHistoryResponse(BaseModel):
    items: List[DrugIdentifyHistoryItem]
    total: int


class ConversationMessageItem(BaseModel):
    role: str
    content: str
    image_urls: Optional[Any] = None
    created_at: Optional[datetime] = None


class ConversationResponse(BaseModel):
    messages: List[ConversationMessageItem]
