from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ServiceCategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0


class ServiceCategoryResponse(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceItemCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    images: Optional[Any] = None
    service_type: str = "online"
    stock: int = 0


class ServiceItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    images: Optional[Any] = None
    service_type: Optional[str] = None
    stock: Optional[int] = None
    status: Optional[str] = None


class ServiceItemResponse(BaseModel):
    id: int
    category_id: int
    name: str
    description: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    images: Optional[Any] = None
    service_type: str
    stock: int
    sales_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
