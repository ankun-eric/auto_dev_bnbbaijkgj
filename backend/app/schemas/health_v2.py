from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class RelationTypeResponse(BaseModel):
    id: int
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class DiseasePresetResponse(BaseModel):
    id: int
    name: str
    category: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class HealthProfileV2Update(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    exercise_habit: Optional[str] = None
    sleep_habit: Optional[str] = None
    diet_habit: Optional[str] = None
    chronic_diseases: Optional[List[str]] = None
    medical_histories: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    drug_allergies: Optional[str] = None
    food_allergies: Optional[str] = None
    other_allergies: Optional[str] = None
    genetic_diseases: Optional[List[str]] = None


class HealthProfileV2Response(BaseModel):
    id: int
    user_id: int
    family_member_id: Optional[int] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    exercise_habit: Optional[str] = None
    sleep_habit: Optional[str] = None
    diet_habit: Optional[str] = None
    chronic_diseases: Optional[List[Any]] = None
    medical_histories: Optional[List[Any]] = None
    allergies: Optional[List[Any]] = None
    drug_allergies: Optional[str] = None
    food_allergies: Optional[str] = None
    other_allergies: Optional[str] = None
    genetic_diseases: Optional[List[Any]] = None
    completeness: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_completeness(self) -> "HealthProfileV2Response":
        fields = [self.name, self.gender, self.birthday, self.height, self.weight, self.blood_type]
        filled = sum(1 for f in fields if f is not None)
        self.completeness = round(filled / len(fields), 2)
        return self


class HealthGuideStatusResponse(BaseModel):
    should_show_guide: bool
    guide_count: int
    profile_completeness: float

    model_config = ConfigDict(from_attributes=True)


class HealthGuideUpdateRequest(BaseModel):
    action: str  # "skip" or "complete"


class HealthGuideUpdateResponse(BaseModel):
    guide_count: int
