from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_global: bool = False


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_global: Optional[bool] = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str = "active"
    is_global: bool = False
    entry_count: int = 0
    active_entry_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeEntryCreate(BaseModel):
    type: str
    question: Optional[str] = None
    title: Optional[str] = None
    content_json: Optional[Any] = None
    keywords: Optional[list[str]] = None
    display_mode: str = "direct"
    status: str = "active"


class KnowledgeEntryUpdate(BaseModel):
    type: Optional[str] = None
    question: Optional[str] = None
    title: Optional[str] = None
    content_json: Optional[Any] = None
    keywords: Optional[list[str]] = None
    display_mode: Optional[str] = None
    status: Optional[str] = None


class KnowledgeEntryResponse(BaseModel):
    id: int
    kb_id: int
    type: str
    question: Optional[str] = None
    title: Optional[str] = None
    content_json: Optional[Any] = None
    keywords: Optional[list[str]] = None
    display_mode: str = "direct"
    status: str = "active"
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSearchConfigSchema(BaseModel):
    scope: str
    config_json: Optional[dict[str, Any]] = None


class KnowledgeFallbackConfigSchema(BaseModel):
    scene: str
    strategy: str = "ai_fallback"
    custom_text: Optional[str] = None
    recommend_count: int = 3


class KnowledgeSceneBindingSchema(BaseModel):
    scene: str
    kb_id: int
    is_primary: bool = True


class KnowledgeHitLogResponse(BaseModel):
    id: int
    entry_id: int
    kb_id: int
    match_type: str
    match_score: Optional[float] = None
    user_question: Optional[str] = None
    search_time_ms: Optional[int] = None
    user_feedback: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeMissedQuestionResponse(BaseModel):
    id: int
    question: str
    scene: Optional[str] = None
    count: int = 1
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeImportRequest(BaseModel):
    kb_id: int
    source_type: str = "excel"
    entries: list[KnowledgeEntryCreate] = []


class KnowledgeImportTaskResponse(BaseModel):
    id: int
    kb_id: int
    source_type: str
    status: str
    result_json: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatsOverview(BaseModel):
    total_knowledge_bases: int = 0
    total_entries: int = 0
    active_entries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    hit_rate: float = 0.0
    avg_search_time_ms: float = 0.0


class TopHitItem(BaseModel):
    entry_id: int
    question: Optional[str] = None
    title: Optional[str] = None
    hit_count: int = 0
    kb_name: Optional[str] = None


class TrendPoint(BaseModel):
    date: str
    hits: int = 0
    misses: int = 0


class ChatFeedbackRequest(BaseModel):
    hit_log_id: int
    feedback: str
