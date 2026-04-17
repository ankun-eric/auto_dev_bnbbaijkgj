from typing import Optional

from pydantic import BaseModel, ConfigDict


class TCMConfigResponse(BaseModel):
    tongue_diagnosis_enabled: bool
    face_diagnosis_enabled: bool
    constitution_test_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class TCMConfigUpdate(BaseModel):
    tongue_diagnosis_enabled: Optional[bool] = None
    face_diagnosis_enabled: Optional[bool] = None
    constitution_test_enabled: Optional[bool] = None
