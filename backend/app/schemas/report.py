from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── Indicator ────────────────


class IndicatorResponse(BaseModel):
    id: int
    report_id: int
    indicator_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: str
    category: Optional[str] = None
    advice: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── Report ────────────────


class ReportUploadResponse(BaseModel):
    id: int
    file_url: str
    thumbnail_url: Optional[str] = None
    file_type: str
    status: str
    message: str


class ReportDetailResponse(BaseModel):
    id: int
    user_id: int
    report_date: Optional[date] = None
    report_type: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_type: Optional[str] = None
    ocr_result: Optional[Any] = None
    ai_analysis: Optional[str] = None
    ai_analysis_json: Optional[Any] = None
    abnormal_count: int = 0
    health_score: Optional[int] = None
    status: Optional[str] = None
    indicators: List[IndicatorResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportListItem(BaseModel):
    id: int
    report_date: Optional[date] = None
    report_type: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_type: Optional[str] = None
    abnormal_count: int = 0
    health_score: Optional[int] = None
    ai_analysis_json: Optional[Any] = None
    status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    items: List[ReportListItem]
    total: int
    page: int
    page_size: int


# ──────────────── Analysis ────────────────


class IndicatorDetail(BaseModel):
    name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: str
    advice: Optional[str] = None


class CategoryView(BaseModel):
    category_name: str
    indicators: List[IndicatorDetail] = []


class ReportAnalysisResponse(BaseModel):
    report_id: int
    status: str
    categories: List[CategoryView] = []
    abnormal_indicators: List[IndicatorDetail] = []
    normal_indicators: List[IndicatorDetail] = []
    overall_assessment: Optional[str] = None
    suggestions: List[str] = []
    disclaimer: str = ""


# ──────────────── Enhanced Analysis ────────────────


class HealthScoreInfo(BaseModel):
    score: int
    level: str
    comment: str


class SummaryInfo(BaseModel):
    totalItems: int
    abnormalCount: int
    excellentCount: int
    normalCount: int


class IndicatorDetailAdvice(BaseModel):
    explanation: Optional[str] = None
    possibleCauses: Optional[str] = None
    dietAdvice: Optional[str] = None
    exerciseAdvice: Optional[str] = None
    lifestyleAdvice: Optional[str] = None
    recheckAdvice: Optional[str] = None
    medicalAdvice: Optional[str] = None


class EnhancedIndicatorItem(BaseModel):
    name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    referenceRange: Optional[str] = None
    riskLevel: int = 2
    riskName: str = "正常"
    detail: Optional[IndicatorDetailAdvice] = None


class EnhancedCategoryView(BaseModel):
    name: str
    emoji: str = "📋"
    items: List[EnhancedIndicatorItem] = []


class EnhancedReportAnalysisResponse(BaseModel):
    report_id: int
    status: str
    healthScore: Optional[HealthScoreInfo] = None
    summary: Optional[SummaryInfo] = None
    categories: List[EnhancedCategoryView] = []
    disclaimer: str = ""


# ──────────────── Report Comparison ────────────────


class CompareIndicatorItem(BaseModel):
    name: str
    previousValue: Optional[str] = None
    currentValue: Optional[str] = None
    unit: Optional[str] = None
    change: Optional[str] = None
    direction: Optional[str] = None
    previousRiskLevel: Optional[int] = None
    currentRiskLevel: Optional[int] = None
    suggestion: Optional[str] = None


class CompareScoreDiff(BaseModel):
    previousScore: Optional[int] = None
    currentScore: Optional[int] = None
    diff: Optional[int] = None
    comment: Optional[str] = None


class ReportCompareResponse(BaseModel):
    aiSummary: Optional[str] = None
    scoreDiff: Optional[CompareScoreDiff] = None
    indicators: List[CompareIndicatorItem] = []
    disclaimer: str = ""


# ──────────────── Trend ────────────────


class TrendDataPoint(BaseModel):
    report_id: int
    report_date: Optional[date] = None
    value: Optional[str] = None
    status: str
    created_at: datetime


class TrendDataResponse(BaseModel):
    indicator_name: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    data_points: List[TrendDataPoint] = []


class TrendAnalysisRequest(BaseModel):
    indicator_name: str


class TrendAnalysisResponse(BaseModel):
    indicator_name: str
    analysis: str
    disclaimer: str = ""


# ──────────────── Alert ────────────────


class AlertResponse(BaseModel):
    id: int
    report_id: int
    indicator_name: str
    alert_type: str
    alert_message: Optional[str] = None
    is_read: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    page: int
    page_size: int


# ──────────────── Share ────────────────


class ShareCreateResponse(BaseModel):
    share_url: str
    share_token: str
    expires_at: datetime


class ShareViewResponse(BaseModel):
    report_date: Optional[date] = None
    report_type: Optional[str] = None
    ai_analysis: Optional[str] = None
    ai_analysis_json: Optional[Any] = None
    abnormal_count: int = 0
    indicators: List[IndicatorResponse] = []
    disclaimer: str = ""


# ──────────────── OCR Config ────────────────


class OcrConfigResponse(BaseModel):
    id: int
    enabled: bool
    api_key: Optional[str] = None
    ocr_type: str
    token_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OcrConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    ocr_type: Optional[str] = None
