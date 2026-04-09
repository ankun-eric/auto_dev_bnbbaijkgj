from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BottomNavCreate(BaseModel):
    name: str = Field(..., max_length=6)
    icon_key: str = Field(..., max_length=50)
    path: str = Field(..., max_length=200)
    is_visible: bool = Field(default=True)


class BottomNavUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=6)
    icon_key: Optional[str] = Field(None, max_length=50)
    path: Optional[str] = Field(None, max_length=200)
    is_visible: Optional[bool] = None


class BottomNavResponse(BaseModel):
    id: int
    name: str
    icon_key: str
    path: str
    sort_order: int
    is_visible: bool
    is_fixed: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BottomNavSortItem(BaseModel):
    id: int
    sort_order: int
