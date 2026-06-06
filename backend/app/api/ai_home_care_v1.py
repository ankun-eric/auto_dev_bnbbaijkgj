"""
[PRD-AIHOME-CARE-V1 2026-05-27]
AI 首页优化 PRD · 关怀版 v1.0
- 用户偏好（关怀/标准模式 + SOS 悬浮球开关）
- SOS 关键词配置 + 触发检测
- SOS 事件记录
- AI 主动推送卡片聚合（健康简报/用药提醒/居家安全/SOS 关怀）
- 拍照问 AI 入口（沿用现有 chat 流程，本模块不重复实现）

采用独立模块、独立表前缀 `care_v1_`，不破坏任何现有功能。
表通过 SQLAlchemy metadata + startup 时自动建表。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, JSON, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_db
from app.core.security import get_current_user

router = APIRouter(tags=["AI首页关怀版V1"])


# ==================== 数据模型 ====================
class CareV1UserPreference(Base):
    __tablename__ = "care_v1_user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    ui_mode = Column(String(16), nullable=False, default="standard")  # care / standard
    ui_mode_set_at = Column(DateTime, nullable=True)
    ui_mode_first_choice = Column(Boolean, nullable=False, default=False)
    sos_floating_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class CareV1SosEvent(Base):
    __tablename__ = "care_v1_sos_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    trigger_source = Column(String(32), nullable=False)
    trigger_keyword = Column(String(128), nullable=True)
    trigger_text = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="pending")
    countdown_remaining_ms = Column(Integer, nullable=True)
    location_lat = Column(String(32), nullable=True)
    location_lng = Column(String(32), nullable=True)
    health_snapshot_json = Column(JSON, nullable=True)
    notified_family_user_ids = Column(JSON, nullable=True)
    call_120_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class CareV1SosKeyword(Base):
    __tablename__ = "care_v1_sos_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(32), nullable=False, index=True)  # high_risk / symptom / degree / negation
    keyword = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class CareV1ProactiveCardLog(Base):
    __tablename__ = "care_v1_proactive_card_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    card_type = Column(String(32), nullable=False)
    card_content_json = Column(JSON, nullable=True)
    shown_at = Column(DateTime, nullable=False, default=datetime.now)
    user_action = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class CareV1VitalMeasurement(Base):
    __tablename__ = "care_v1_vital_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    metric_type = Column(String(32), nullable=False)
    value_systolic = Column(Integer, nullable=True)
    value_diastolic = Column(Integer, nullable=True)
    value_numeric = Column(String(32), nullable=True)
    value_unit = Column(String(16), nullable=True)
    measured_at = Column(DateTime, nullable=False, default=datetime.now)
    source = Column(String(32), nullable=False, default="manual")
    device_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class CareV1UserDevice(Base):
    __tablename__ = "care_v1_user_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_type = Column(String(32), nullable=False)
    device_name = Column(String(64), nullable=True)
    device_serial = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="online")
    battery_level = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


# ==================== Schemas ====================
class UiModeUpdate(BaseModel):
    ui_mode: str
    first_choice: Optional[bool] = None
    sos_floating_enabled: Optional[bool] = None


# ==================== 用户偏好 ====================
@router.get("/api/care-v1/user-preferences")
async def get_user_preferences(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CareV1UserPreference).where(CareV1UserPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = CareV1UserPreference(user_id=current_user.id, ui_mode="standard")
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return {
        "code": 200,
        "data": {
            "ui_mode": pref.ui_mode,
            "ui_mode_first_choice": pref.ui_mode_first_choice,
            "sos_floating_enabled": pref.sos_floating_enabled,
            "ui_mode_set_at": pref.ui_mode_set_at.isoformat() if pref.ui_mode_set_at else None,
        },
    }


@router.put("/api/care-v1/user-preferences/ui-mode")
async def update_ui_mode(
    body: UiModeUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.ui_mode not in ("care", "standard"):
        raise HTTPException(status_code=400, detail="ui_mode 只能是 care 或 standard")
    result = await db.execute(
        select(CareV1UserPreference).where(CareV1UserPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = CareV1UserPreference(user_id=current_user.id)
        db.add(pref)
    pref.ui_mode = body.ui_mode
    pref.ui_mode_set_at = datetime.now()
    if body.first_choice is not None:
        pref.ui_mode_first_choice = body.first_choice
    if body.sos_floating_enabled is not None:
        pref.sos_floating_enabled = body.sos_floating_enabled
    await db.commit()
    await db.refresh(pref)
    return {
        "code": 200,
        "data": {
            "ui_mode": pref.ui_mode,
            "ui_mode_first_choice": pref.ui_mode_first_choice,
            "sos_floating_enabled": pref.sos_floating_enabled,
        },
    }
