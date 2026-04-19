from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Menu Item Schemas ──

class HomeMenuItemCreate(BaseModel):
    name: str = Field(..., max_length=20)
    icon_type: str = Field(default="emoji")
    icon_content: str = Field(..., max_length=500)
    link_type: str = Field(default="internal")
    link_url: str = Field(..., max_length=500)
    miniprogram_appid: Optional[str] = Field(None, max_length=100)
    sort_order: int = Field(default=0)
    is_visible: bool = Field(default=True)


class HomeMenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=20)
    icon_type: Optional[str] = None
    icon_content: Optional[str] = Field(None, max_length=500)
    link_type: Optional[str] = None
    link_url: Optional[str] = Field(None, max_length=500)
    miniprogram_appid: Optional[str] = Field(None, max_length=100)
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None


class HomeMenuItemResponse(BaseModel):
    id: int
    name: str
    icon_type: str
    icon_content: str
    link_type: str
    link_url: str
    miniprogram_appid: Optional[str] = None
    sort_order: int
    is_visible: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Banner Schemas ──

class HomeBannerCreate(BaseModel):
    image_url: str = Field(..., max_length=500)
    link_type: str = Field(default="none")
    link_url: Optional[str] = Field(None, max_length=500)
    miniprogram_appid: Optional[str] = Field(None, max_length=100)
    sort_order: int = Field(default=0)
    is_visible: bool = Field(default=True)


class HomeBannerUpdate(BaseModel):
    image_url: Optional[str] = Field(None, max_length=500)
    link_type: Optional[str] = None
    link_url: Optional[str] = Field(None, max_length=500)
    miniprogram_appid: Optional[str] = Field(None, max_length=100)
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None


class HomeBannerResponse(BaseModel):
    id: int
    image_url: str
    link_type: str
    link_url: Optional[str] = None
    miniprogram_appid: Optional[str] = None
    sort_order: int
    is_visible: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Home Config Schemas ──

class HomeConfigResponse(BaseModel):
    search_visible: bool = True
    search_placeholder: str = ""
    grid_columns: int = 3
    font_switch_enabled: bool = True
    font_default_level: str = "standard"
    font_standard_size: int = 16
    font_large_size: int = 19
    font_xlarge_size: int = 22


class HomeConfigUpdate(BaseModel):
    search_visible: Optional[bool] = None
    search_placeholder: Optional[str] = None
    grid_columns: Optional[int] = None
    font_switch_enabled: Optional[bool] = None
    font_default_level: Optional[str] = None
    font_standard_size: Optional[int] = None
    font_large_size: Optional[int] = None
    font_xlarge_size: Optional[int] = None


# ── Sort Schema ──

class SortItem(BaseModel):
    id: int
    sort_order: int
