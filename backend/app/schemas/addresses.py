from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AddressCreate(BaseModel):
    name: str
    phone: str
    province: str
    city: str
    district: str
    street: str
    is_default: bool = False


class AddressUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    is_default: Optional[bool] = None


class AddressResponse(BaseModel):
    id: int
    user_id: int
    name: str
    phone: str
    province: str
    city: str
    district: str
    street: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
