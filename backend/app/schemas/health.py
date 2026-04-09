from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class HealthProfileCreate(BaseModel):
    family_member_id: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    exercise_habit: Optional[str] = None
    sleep_habit: Optional[str] = None
    diet_habit: Optional[str] = None
    medical_histories: Optional[List[str]] = None
    allergies: Optional[List[str]] = None


class HealthProfileUpdate(BaseModel):
    family_member_id: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    exercise_habit: Optional[str] = None
    sleep_habit: Optional[str] = None
    diet_habit: Optional[str] = None
    medical_histories: Optional[List[str]] = None
    allergies: Optional[List[str]] = None


class HealthProfileResponse(BaseModel):
    id: int
    user_id: int
    family_member_id: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    exercise_habit: Optional[str] = None
    sleep_habit: Optional[str] = None
    diet_habit: Optional[str] = None
    medical_histories: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AllergyCreate(BaseModel):
    allergy_type: str
    allergy_name: str
    severity: Optional[str] = None


class AllergyResponse(BaseModel):
    id: int
    user_id: int
    allergy_type: str
    allergy_name: str
    severity: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicalHistoryCreate(BaseModel):
    disease_name: str
    diagnosis_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class MedicalHistoryResponse(BaseModel):
    id: int
    user_id: int
    disease_name: str
    diagnosis_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicationCreate(BaseModel):
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = "active"


class MedicationResponse(BaseModel):
    id: int
    user_id: int
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VisitRecordCreate(BaseModel):
    hospital: Optional[str] = None
    department: Optional[str] = None
    diagnosis: Optional[str] = None
    visit_date: Optional[date] = None
    notes: Optional[str] = None


class VisitRecordResponse(BaseModel):
    id: int
    user_id: int
    hospital: Optional[str] = None
    department: Optional[str] = None
    diagnosis: Optional[str] = None
    visit_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckupIndicatorResponse(BaseModel):
    id: int
    report_id: int
    indicator_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckupReportResponse(BaseModel):
    id: int
    user_id: int
    report_date: Optional[date] = None
    report_type: Optional[str] = None
    file_url: Optional[str] = None
    ocr_result: Optional[Any] = None
    ai_analysis: Optional[str] = None
    indicators: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
