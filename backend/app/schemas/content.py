from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class ArticleCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    content_html: Optional[str] = None
    cover_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[Any] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    is_top: Optional[bool] = False
    author_name: Optional[str] = None
    published_at: Optional[datetime] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_html: Optional[str] = None
    cover_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[Any] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    is_top: Optional[bool] = None
    author_name: Optional[str] = None
    published_at: Optional[datetime] = None


class ArticleResponse(BaseModel):
    id: int
    title: str
    content: Optional[str] = ""
    content_html: Optional[str] = None
    cover_image: Optional[str] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[Any] = None
    summary: Optional[str] = None
    view_count: int
    like_count: int
    comment_count: Optional[int] = 0
    is_top: Optional[bool] = False
    status: str
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# v8: 文章分类
class ArticleCategoryCreate(BaseModel):
    name: str
    sort_order: Optional[int] = 0
    is_enabled: Optional[bool] = True


class ArticleCategoryUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    is_enabled: Optional[bool] = None


class ArticleCategoryResponse(BaseModel):
    id: int
    name: str
    sort_order: int
    is_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# v8: 资讯
class NewsCreate(BaseModel):
    title: str
    cover_image: Optional[str] = None
    summary: Optional[str] = None
    content_html: str
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    status: Optional[str] = "draft"
    is_top: Optional[bool] = False
    published_at: Optional[datetime] = None


class NewsUpdate(BaseModel):
    title: Optional[str] = None
    cover_image: Optional[str] = None
    summary: Optional[str] = None
    content_html: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    status: Optional[str] = None
    is_top: Optional[bool] = None
    published_at: Optional[datetime] = None


class NewsResponse(BaseModel):
    id: int
    title: str
    cover_image: Optional[str] = None
    summary: Optional[str] = None
    content_html: str
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    status: str
    is_top: bool
    view_count: int
    like_count: int
    comment_count: int
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, obj):
        tag_list: List[str] = []
        if obj.tags:
            tag_list = [t.strip() for t in str(obj.tags).split(",") if t.strip()]
        return cls(
            id=obj.id,
            title=obj.title,
            cover_image=obj.cover_image,
            summary=obj.summary,
            content_html=obj.content_html or "",
            tags=tag_list,
            source=obj.source,
            status=obj.status.value if hasattr(obj.status, "value") else str(obj.status),
            is_top=bool(obj.is_top),
            view_count=obj.view_count or 0,
            like_count=obj.like_count or 0,
            comment_count=obj.comment_count or 0,
            published_at=obj.published_at,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class NewsTagSuggestItem(BaseModel):
    tag: str
    use_count: int


class CommentCreate(BaseModel):
    content_type: str
    content_id: int
    content: str
    parent_id: Optional[int] = None


class CommentResponse(BaseModel):
    id: int
    content_type: str
    content_id: int
    user_id: int
    parent_id: Optional[int] = None
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
