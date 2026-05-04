"""[2026-05-05 用户地址改造 PRD v1.0] 用户地址 v2 Schema。

新字段：consignee_name / consignee_phone / province_code / city_code / district_code
       / detail（替代 street）/ longitude / latitude / tag / is_deleted
保留旧字段（v1 兼容）：name / phone / street
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class AddressV2Base(BaseModel):
    consignee_name: str = Field(..., min_length=1, max_length=20, description="收货人姓名")
    consignee_phone: str = Field(..., description="11 位中国大陆手机号")
    province: str = Field(..., min_length=1, max_length=20)
    province_code: Optional[str] = Field(None, max_length=6)
    city: str = Field(..., min_length=1, max_length=20)
    city_code: Optional[str] = Field(None, max_length=6)
    district: str = Field(..., min_length=1, max_length=20)
    district_code: Optional[str] = Field(None, max_length=6)
    detail: str = Field(..., min_length=1, max_length=80, description="详细地址，最多 80 字")
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    tag: Optional[str] = Field(None, max_length=12, description="标签：家/公司/自定义≤6 汉字或 12 字符")
    is_default: bool = False

    @field_validator("consignee_phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        if not _PHONE_RE.match(v):
            raise ValueError("手机号格式不正确（需 11 位，1[3-9] 开头）")
        return v


class AddressV2Create(AddressV2Base):
    pass


class AddressV2Update(BaseModel):
    consignee_name: Optional[str] = Field(None, min_length=1, max_length=20)
    consignee_phone: Optional[str] = None
    province: Optional[str] = Field(None, max_length=20)
    province_code: Optional[str] = Field(None, max_length=6)
    city: Optional[str] = Field(None, max_length=20)
    city_code: Optional[str] = Field(None, max_length=6)
    district: Optional[str] = Field(None, max_length=20)
    district_code: Optional[str] = Field(None, max_length=6)
    detail: Optional[str] = Field(None, max_length=80)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    tag: Optional[str] = Field(None, max_length=12)
    is_default: Optional[bool] = None

    @field_validator("consignee_phone")
    @classmethod
    def _check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _PHONE_RE.match(v):
            raise ValueError("手机号格式不正确（需 11 位，1[3-9] 开头）")
        return v


class AddressV2Response(BaseModel):
    id: int
    user_id: int
    consignee_name: Optional[str] = None
    consignee_phone: Optional[str] = None
    province: Optional[str] = None
    province_code: Optional[str] = None
    city: Optional[str] = None
    city_code: Optional[str] = None
    district: Optional[str] = None
    district_code: Optional[str] = None
    detail: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    tag: Optional[str] = None
    is_default: bool = False
    needs_region_completion: bool = Field(default=False, description="老数据待补全省市县")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SetDefaultRequest(BaseModel):
    is_default: bool = True


class ReverseGeocodeRequest(BaseModel):
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)


class ReverseGeocodeResponse(BaseModel):
    province: str = ""
    province_code: str = ""
    city: str = ""
    city_code: str = ""
    district: str = ""
    district_code: str = ""
    detail: str = ""
    formatted_address: str = ""
    provider: str = "amap"


class VersionCheckResponse(BaseModel):
    minVersion: str
    latestVersion: str
    forceUpgrade: bool
    downloadUrl: str
    upgradeMessage: str
