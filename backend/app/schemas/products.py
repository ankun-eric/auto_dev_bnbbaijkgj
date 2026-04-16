from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProductCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0
    status: str = "active"
    level: int = 1


class ProductCategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None


class ProductCategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int
    status: str
    level: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductCategoryTreeResponse(ProductCategoryResponse):
    children: list["ProductCategoryTreeResponse"] = []


class ProductCreate(BaseModel):
    name: str
    category_id: int
    fulfillment_type: str
    original_price: float
    sale_price: float
    images: Optional[Any] = None
    video_url: Optional[str] = None
    description: Optional[str] = None
    symptom_tags: Optional[Any] = None
    stock: int = 0
    valid_start_date: Optional[date] = None
    valid_end_date: Optional[date] = None
    points_exchangeable: bool = False
    points_price: int = 0
    points_deductible: bool = False
    redeem_count: int = 1
    appointment_mode: str = "none"
    purchase_appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
    faq: Optional[Any] = None
    recommend_weight: int = 0
    status: str = "draft"
    sort_order: int = 0
    payment_timeout_minutes: int = 15
    store_ids: Optional[list[int]] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    fulfillment_type: Optional[str] = None
    original_price: Optional[float] = None
    sale_price: Optional[float] = None
    images: Optional[Any] = None
    video_url: Optional[str] = None
    description: Optional[str] = None
    symptom_tags: Optional[Any] = None
    stock: Optional[int] = None
    valid_start_date: Optional[date] = None
    valid_end_date: Optional[date] = None
    points_exchangeable: Optional[bool] = None
    points_price: Optional[int] = None
    points_deductible: Optional[bool] = None
    redeem_count: Optional[int] = None
    appointment_mode: Optional[str] = None
    purchase_appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
    faq: Optional[Any] = None
    recommend_weight: Optional[int] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
    payment_timeout_minutes: Optional[int] = None
    store_ids: Optional[list[int]] = None


class ProductStoreResponse(BaseModel):
    id: int
    store_id: int
    store_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    id: int
    name: str
    category_id: int
    fulfillment_type: str
    original_price: float
    sale_price: float
    images: Optional[Any] = None
    video_url: Optional[str] = None
    description: Optional[str] = None
    symptom_tags: Optional[Any] = None
    stock: int
    valid_start_date: Optional[date] = None
    valid_end_date: Optional[date] = None
    points_exchangeable: bool
    points_price: int
    points_deductible: bool
    redeem_count: int
    appointment_mode: str
    purchase_appointment_mode: Optional[str] = None
    custom_form_id: Optional[int] = None
    faq: Optional[Any] = None
    recommend_weight: int
    sales_count: int
    status: str
    sort_order: int
    payment_timeout_minutes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductDetailResponse(ProductResponse):
    stores: list[ProductStoreResponse] = []
    review_count: int = 0
    avg_rating: Optional[float] = None
    category_name: Optional[str] = None


class AppointmentFormCreate(BaseModel):
    name: str
    description: Optional[str] = None


class AppointmentFormResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentFormFieldCreate(BaseModel):
    field_type: str
    label: str
    placeholder: Optional[str] = None
    required: bool = False
    options: Optional[Any] = None
    sort_order: int = 0


class AppointmentFormFieldUpdate(BaseModel):
    field_type: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    required: Optional[bool] = None
    options: Optional[Any] = None
    sort_order: Optional[int] = None


class AppointmentFormFieldResponse(BaseModel):
    id: int
    form_id: int
    field_type: str
    label: str
    placeholder: Optional[str] = None
    required: bool
    options: Optional[Any] = None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SymptomTagResponse(BaseModel):
    tag: str
    count: int
