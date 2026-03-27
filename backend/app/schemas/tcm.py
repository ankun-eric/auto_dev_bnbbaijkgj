from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class TCMDiagnosisCreate(BaseModel):
    tongue_image_url: Optional[str] = None
    face_image_url: Optional[str] = None


class TCMDiagnosisResponse(BaseModel):
    id: int
    user_id: int
    tongue_image_url: Optional[str] = None
    face_image_url: Optional[str] = None
    constitution_type: Optional[str] = None
    tongue_analysis: Optional[str] = None
    face_analysis: Optional[str] = None
    syndrome_analysis: Optional[str] = None
    health_plan: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConstitutionQuestionResponse(BaseModel):
    id: int
    question_text: str
    question_group: Optional[str] = None
    options: Optional[Any] = None
    order_num: int

    model_config = ConfigDict(from_attributes=True)


class ConstitutionAnswerCreate(BaseModel):
    question_id: int
    answer_value: str


class ConstitutionTestRequest(BaseModel):
    answers: List[ConstitutionAnswerCreate]
