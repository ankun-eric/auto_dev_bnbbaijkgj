from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ──────────────── 搜索历史 ────────────────


class SearchHistoryResponse(BaseModel):
    id: int
    keyword: str
    search_count: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 搜索热词 ────────────────


class SearchHotWordResponse(BaseModel):
    id: int
    keyword: str
    search_count: int
    result_count: int
    category_hint: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 推荐搜索词 ────────────────


class SearchRecommendWordCreate(BaseModel):
    keyword: str
    sort_order: int = 0
    category_hint: Optional[str] = None
    is_active: bool = True


class SearchRecommendWordUpdate(BaseModel):
    keyword: Optional[str] = None
    sort_order: Optional[int] = None
    category_hint: Optional[str] = None
    is_active: Optional[bool] = None


class SearchRecommendWordResponse(BaseModel):
    id: int
    keyword: str
    sort_order: int
    category_hint: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── 屏蔽词 ────────────────


class SearchBlockWordCreate(BaseModel):
    keyword: str
    block_mode: str = "full"
    tip_content: Optional[str] = None
    is_active: bool = True


class SearchBlockWordUpdate(BaseModel):
    keyword: Optional[str] = None
    block_mode: Optional[str] = None
    tip_content: Optional[str] = None
    is_active: Optional[bool] = None


class SearchBlockWordResponse(BaseModel):
    id: int
    keyword: str
    block_mode: str
    tip_content: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchBlockWordBatchImport(BaseModel):
    keywords: list[str]
    block_mode: str = "full"
    tip_content: Optional[str] = None


# ──────────────── 搜索日志 ────────────────


class SearchLogCreate(BaseModel):
    keyword: str
    clicked_type: Optional[str] = None
    clicked_item_id: Optional[int] = None


class SearchLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    keyword: str
    result_count: int
    clicked_type: Optional[str] = None
    clicked_item_id: Optional[int] = None
    source: str
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────── ASR 配置 ────────────────


class AsrConfigResponse(BaseModel):
    id: int
    provider: str
    app_id: Optional[str] = None
    secret_id: Optional[str] = None
    secret_key_encrypted: Optional[str] = None
    is_enabled: bool
    supported_dialects: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AsrConfigUpdate(BaseModel):
    provider: Optional[str] = None
    app_id: Optional[str] = None
    secret_id: Optional[str] = None
    secret_key_raw: Optional[str] = None
    is_enabled: Optional[bool] = None
    supported_dialects: Optional[str] = None


# ──────────────── 统一搜索结果 ────────────────


class SearchResultItem(BaseModel):
    id: int
    type: str
    title: str
    summary: Optional[str] = None
    cover_image: Optional[str] = None
    tags: Optional[Any] = None
    score: float = 0.0


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    type_counts: dict[str, int]
    block_tip: Optional[str] = None
    page: int
    page_size: int


class SearchSuggestItem(BaseModel):
    keyword: str
    category_hint: Optional[str] = None
    is_drug_keyword: bool = False


# ──────────────── 搜索统计 ────────────────


class SearchStatisticsResponse(BaseModel):
    top_keywords: list[dict]
    trend: list[dict]
    no_result_keywords: list[dict]
    type_distribution: dict[str, int]


# ──────────────── 拍照识药关键词 ────────────────


class DrugSearchKeywordResponse(BaseModel):
    id: int
    keyword: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
