"""[PRD-TAG-RECOMMEND-V1 2026-05-20]
标签管理 + 问卷推荐配置 Pydantic Schema
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# [商品标签体系重构 v1.0 2026-05-20] 6 类分类枚举（不再包含 service/other）
TAG_CATEGORIES = (
    "constitution",      # 体质类（预置 9 体质，锁定）
    "symptom",           # 症状类
    "crowd",             # 人群类
    "effect",            # 功效类
    "scene",             # 场景类
    "contraindication",  # 禁忌类
)

# 9 种体质，统一为 constitution 类下预置标签，is_locked=1
CONSTITUTION_PRESET_NAMES = (
    "平和质", "气虚质", "阳虚质", "阴虚质",
    "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质",
)


# ──────────────── Tag ────────────────


class TagBase(BaseModel):
    name: str = Field(..., max_length=64)
    category: str = Field(..., max_length=32)
    status: Optional[int] = 1
    sort_order: Optional[int] = 0


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[int] = None
    sort_order: Optional[int] = None


class TagResponse(TagBase):
    id: int
    goods_count: Optional[int] = 0
    is_locked: Optional[int] = 0
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
