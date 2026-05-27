"""
[BUG_FIX_CARE_MODE_ENTRY_H5_20260527] 关怀模式入口缺失修复 — 用户模式偏好接口

提供 GET / POST /api/user/mode-preference 两个端点，用于持久化用户在
H5/小程序/APP 上选择的"标准模式 / 关怀模式"。

设计要点：
- 单独建表 user_mode_preferences，避免改动 users 表造成迁移影响
- mode 字段仅允许 'standard' | 'care'
- 用户从未设置时 GET 返回 'standard'
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column
from sqlalchemy import Integer, String, DateTime

from app.core.database import Base, get_db
from app.core.security import get_current_user
from app.models.models import User


class UserModePreference(Base):
    """用户模式偏好（standard / care）"""

    __tablename__ = "user_mode_preferences"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, nullable=False, unique=True, index=True)
    mode = mapped_column(String(16), nullable=False, default="standard")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


router = APIRouter(prefix="/api/user", tags=["用户模式偏好"])


class ModeOut(BaseModel):
    mode: Literal["standard", "care"] = Field(..., description="用户当前模式偏好")


class ModeIn(BaseModel):
    mode: Literal["standard", "care"]


class SaveResult(BaseModel):
    success: bool = True
    mode: Literal["standard", "care"]


@router.get("/mode-preference", response_model=ModeOut)
async def get_mode_preference(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(UserModePreference).where(UserModePreference.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        return ModeOut(mode="standard")
    mode = row.mode if row.mode in ("standard", "care") else "standard"
    return ModeOut(mode=mode)  # type: ignore[arg-type]


@router.post("/mode-preference", response_model=SaveResult)
async def save_mode_preference(
    data: ModeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(UserModePreference).where(UserModePreference.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserModePreference(user_id=current_user.id, mode=data.mode)
        db.add(row)
    else:
        row.mode = data.mode
        row.updated_at = datetime.utcnow()
    await db.flush()
    return SaveResult(success=True, mode=data.mode)
