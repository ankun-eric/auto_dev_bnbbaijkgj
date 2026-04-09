from typing import Literal

from pydantic import BaseModel


class FontSettingResponse(BaseModel):
    font_size_level: str


class FontSettingUpdate(BaseModel):
    font_size_level: Literal["standard", "large", "extra_large"]
