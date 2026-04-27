from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ExpertCreate(BaseModel):
    user_id: Optional[int] = None
    name: str
    title: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    specialties: Optional[str] = None
    introduction: Optional[str] = None
    avatar: Optional[str] = None
    consultation_fee: float = 0


class ProductBriefInfo(BaseModel):
    id: int
    name: str
    sale_price: float
    status: str

    model_config = ConfigDict(from_attributes=True)


class ExpertResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    title: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    specialties: Optional[str] = None
    introduction: Optional[str] = None
    avatar: Optional[str] = None
    consultation_fee: float
    rating: float
    review_count: int
    status: str
    product_id: Optional[int] = None
    product_info: Optional[ProductBriefInfo] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpertScheduleCreate(BaseModel):
    date: date
    time_slot: str
    max_appointments: int = 10


class ExpertScheduleResponse(BaseModel):
    id: int
    expert_id: int
    date: date
    time_slot: str
    max_appointments: int
    current_appointments: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    expert_id: int
    schedule_id: int
    appointment_date: date
    time_slot: str
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: int
    user_id: int
    expert_id: int
    schedule_id: int
    appointment_date: date
    time_slot: str
    status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
