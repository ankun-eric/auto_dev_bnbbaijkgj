from typing import Optional

from pydantic import BaseModel


class TTSConfigResponse(BaseModel):
    enabled: bool = False
    default_mode: str = "free"
    platform_override: Optional[str] = None
    cloud_provider: Optional[str] = None
    voice_gender: str = "female"
    speed: float = 1.0
    pitch: float = 1.0


class TTSConfigFullResponse(BaseModel):
    enabled: bool = False
    default_mode: str = "free"
    h5_mode: Optional[str] = None
    miniprogram_mode: Optional[str] = None
    app_mode: Optional[str] = None
    cloud_provider: str = "aliyun"
    cloud_api_key: Optional[str] = None
    voice_gender: str = "female"
    speed: float = 1.0
    pitch: float = 1.0


class TTSConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    default_mode: Optional[str] = None
    h5_mode: Optional[str] = None
    miniprogram_mode: Optional[str] = None
    app_mode: Optional[str] = None
    cloud_provider: Optional[str] = None
    cloud_api_key: Optional[str] = None
    voice_gender: Optional[str] = None
    speed: Optional[float] = None
    pitch: Optional[float] = None


class TTSSynthesizeRequest(BaseModel):
    text: str
    voice_gender: Optional[str] = None
    speed: Optional[float] = None
    pitch: Optional[float] = None
