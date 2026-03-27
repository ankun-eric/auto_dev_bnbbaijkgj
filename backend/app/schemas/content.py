from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ArticleCreate(BaseModel):
    title: str
    content: str
    cover_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[Any] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    cover_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[Any] = None
    status: Optional[str] = None


class ArticleResponse(BaseModel):
    id: int
    title: str
    content: str
    cover_image: Optional[str] = None
    author_id: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[Any] = None
    view_count: int
    like_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    video_url: str
    cover_image: Optional[str] = None
    category: Optional[str] = None
    duration: int = 0


class VideoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    video_url: str
    cover_image: Optional[str] = None
    author_id: Optional[int] = None
    category: Optional[str] = None
    duration: int
    view_count: int
    like_count: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
