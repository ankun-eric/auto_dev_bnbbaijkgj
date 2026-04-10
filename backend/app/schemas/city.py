from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CityResponse(BaseModel):
    id: int
    name: str
    short_name: str
    pinyin: str
    first_letter: str
    province: str
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    is_hot: bool = False
    hot_sort: int = 0
    is_active: bool = True

    model_config = {"from_attributes": True}


class CityBrief(BaseModel):
    id: int
    name: str
    short_name: str
    first_letter: str

    model_config = {"from_attributes": True}


class CityGroupResponse(BaseModel):
    letter: str
    cities: List[CityBrief]


class CityListResponse(BaseModel):
    groups: List[CityGroupResponse]
    total: int


class HotCityResponse(BaseModel):
    cities: List[CityBrief]


class LocateResponse(BaseModel):
    city: Optional[CityBrief] = None
    message: str = "ok"


class HotCitySetRequest(BaseModel):
    city_ids: List[int]


class AdminCityListResponse(BaseModel):
    items: List[CityResponse]
    total: int
    page: int
    page_size: int
