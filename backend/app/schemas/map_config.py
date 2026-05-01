"""[2026-05-01 地图配置 PRD v1.0] 地图配置相关 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MapConfigBase(BaseModel):
    provider: str = Field(default="amap", description="地图服务商，本期固定 amap")
    server_key: str = Field(default="", max_length=255, description="高德 Web 服务 Key（后端用）")
    web_js_key: str = Field(default="", max_length=255, description="管理后台浏览器 JS Key")
    h5_js_key: str = Field(default="", max_length=255, description="用户端 H5/APP/小程序 JS Key")
    security_js_code: str = Field(default="", max_length=255, description="高德安全密钥 SecurityJsCode")
    default_city: str = Field(default="北京", max_length=50, description="默认城市")
    default_center_lng: float = Field(default=116.397428, description="默认中心点经度")
    default_center_lat: float = Field(default=39.90923, description="默认中心点纬度")
    default_zoom: int = Field(default=12, ge=3, le=18, description="默认缩放级别 3-18")


class MapConfigUpdate(MapConfigBase):
    """保存配置请求体。"""

    @field_validator("default_center_lng")
    @classmethod
    def _check_lng(cls, v: float) -> float:
        if v < -180 or v > 180:
            raise ValueError("经度必须在 -180 到 180 之间")
        return v

    @field_validator("default_center_lat")
    @classmethod
    def _check_lat(cls, v: float) -> float:
        if v < -90 or v > 90:
            raise ValueError("纬度必须在 -90 到 90 之间")
        return v


class MapConfigResponse(MapConfigBase):
    id: Optional[int] = None
    has_record: bool = False  # 是否存在数据库配置（未保存过则 False）
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True


class MapTestSubResult(BaseModel):
    status: str = Field(description="ok / fail")
    detail: str = Field(default="", description="测试结果说明 / 错误码")


class MapTestResponse(BaseModel):
    server: MapTestSubResult
    web: MapTestSubResult
    h5: MapTestSubResult
    overall_pass: bool
    tested_at: datetime


class MapTestLogItem(BaseModel):
    id: int
    operator_name: Optional[str] = None
    server_status: str
    web_status: str
    h5_status: str
    overall_pass: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MapTestLogsResponse(BaseModel):
    items: List[MapTestLogItem]


class CopyDomainResponse(BaseModel):
    web_admin_origin: str
    h5_origin: str
