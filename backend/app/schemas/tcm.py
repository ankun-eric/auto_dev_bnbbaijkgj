from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator


class TCMDiagnosisCreate(BaseModel):
    tongue_image_url: Optional[str] = None
    face_image_url: Optional[str] = None
    family_member_id: Optional[int] = None


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
    family_member_id: Optional[int] = None
    constitution_description: Optional[str] = None
    advice_summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TCMDiagnosisListResponse(BaseModel):
    id: int
    user_id: int
    constitution_type: Optional[str] = None
    constitution_description: Optional[str] = None
    family_member_id: Optional[int] = None
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
    family_member_id: Optional[int] = None

    @field_validator("answers", mode="before")
    @classmethod
    def _normalize_answers(cls, v: Any):
        """兼容前端可能传入的多种 answers 格式：

        1. List[ConstitutionAnswerCreate] —— 标准格式
        2. Dict[str|int, str] —— 旧版前端格式 {"1": "从不", "2": "偶尔"}
        3. List[Dict[Any, Any]] —— 已经是字典数组，保持不变
        """
        if isinstance(v, dict):
            return [
                {"question_id": int(k), "answer_value": str(val)}
                for k, val in v.items()
            ]
        return v
