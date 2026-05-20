"""[PRD-TAG-RECOMMEND-V1 2026-05-20]
标签管理 + 问卷推荐配置 Pydantic Schema
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# 7 类分类枚举
TAG_CATEGORIES = ("symptom", "effect", "constitution", "crowd", "service", "scene", "other")


# ──────────────── Tag ────────────────


class TagBase(BaseModel):
    name: str = Field(..., max_length=64)
    category: str = Field(..., max_length=32)
    status: Optional[int] = 1


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[int] = None


class TagResponse(TagBase):
    id: int
    goods_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagMergeRequest(BaseModel):
    target_id: int  # 把当前标签合并到 target_id


# ──────────────── 商品标签 ────────────────


class GoodsTagsUpdate(BaseModel):
    tag_ids: list[int]


# ──────────────── 问卷推荐配置 ────────────────


class RecommendFilter(BaseModel):
    """筛选条件 JSON 结构"""
    category_ids: Optional[list[int]] = None
    fulfillment_types: Optional[list[str]] = None
    tag_ids: Optional[list[int]] = None


class RecommendConfigItem(BaseModel):
    result_key: str
    mode: int  # 1=标签智能匹配 2=按标签固定推荐 3=手动挑商品
    filter_json: Optional[dict[str, Any]] = None
    manual_goods_ids: Optional[list[int]] = None


class RecommendConfigBulkUpdate(BaseModel):
    """批量保存某模板下所有分型的推荐配置"""
    items: list[RecommendConfigItem]


class RecommendConfigResponse(BaseModel):
    id: int
    template_id: int
    result_key: str
    mode: int
    filter_json: Optional[dict[str, Any]] = None
    manual_goods_ids: Optional[list[int]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendPreviewRequest(BaseModel):
    result_key: str
    mode: int
    filter_json: Optional[dict[str, Any]] = None
    manual_goods_ids: Optional[list[int]] = None
    limit: Optional[int] = 6


class RecommendGoodsItem(BaseModel):
    """推荐商品卡片渲染数据"""
    id: int
    name: str
    sale_price: float
    original_price: Optional[float] = None
    image: Optional[str] = None
    fulfillment_type: Optional[str] = None
    fulfillment_label: Optional[str] = None
    sales_count: Optional[int] = 0
    hit_tags: Optional[int] = 0


class RecommendPreviewResponse(BaseModel):
    items: list[RecommendGoodsItem]
    total: int
