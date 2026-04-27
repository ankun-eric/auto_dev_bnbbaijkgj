from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class FeedbackCreate(BaseModel):
    feedback_type: str
    description: str
    images: Optional[List[str]] = None
    contact: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    user_id: int
    feedback_type: str
    description: str
    images: Optional[List[str]] = None
    contact: Optional[str] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackStatusUpdate(BaseModel):
    status: str
