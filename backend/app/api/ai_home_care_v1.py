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

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, JSON, select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_db
from app.core.security import get_current_user, require_role

router = APIRouter(tags=["AI首页关怀版V1"])

admin_dep = require_role("admin")


# ==================== 数据模型 ====================
class CareV1UserPreference(Base):
    __tablename__ = "care_v1_user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    ui_mode = Column(String(16), nullable=False, default="standard")  # care / standard
    ui_mode_set_at = Column(DateTime, nullable=True)
    ui_mode_first_choice = Column(Boolean, nullable=False, default=False)
    sos_floating_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class CareV1SosKeyword(Base):
    __tablename__ = "care_v1_sos_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(32), nullable=False, index=True)  # high_risk / symptom / degree / negation
    keyword = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CareV1ProactiveCardLog(Base):
    __tablename__ = "care_v1_proactive_card_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    card_type = Column(String(32), nullable=False)
    card_content_json = Column(JSON, nullable=True)
    shown_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_action = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class CareV1VitalMeasurement(Base):
    __tablename__ = "care_v1_vital_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    metric_type = Column(String(32), nullable=False)
    value_systolic = Column(Integer, nullable=True)
    value_diastolic = Column(Integer, nullable=True)
    value_numeric = Column(String(32), nullable=True)
    value_unit = Column(String(16), nullable=True)
    measured_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String(32), nullable=False, default="manual")
    device_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ==================== 默认关键词种子 ====================
DEFAULT_KEYWORDS: Dict[str, List[str]] = {
    "high_risk": [
        "救命", "晕倒", "昏倒", "摔倒", "说不出话", "嘴歪", "半边脸麻",
        "抽搐", "快不行了", "撑不住了", "打120", "叫救护车",
    ],
    "symptom": [
        "胸闷", "胸痛", "心慌", "心绞痛", "喘不上气", "呼吸困难", "憋气",
        "头晕", "头疼", "眼前发黑", "看不清", "手脚发麻", "麻木",
        "肚子疼", "腹痛", "吐血", "便血", "出冷汗", "浑身没劲", "动不了",
    ],
    "degree": [
        "厉害", "严重", "受不了", "撑不住", "特别", "好难受", "很难受",
        "难受死了", "要命", "没力气", "救救我", "帮帮我",
    ],
    "negation": ["不", "没", "别", "不会", "好多了", "没事"],
}


async def ensure_default_keywords(db: AsyncSession):
    """启动时确保默认关键词存在"""
    exist = await db.execute(select(CareV1SosKeyword).limit(1))
    if exist.scalar_one_or_none():
        return
    for category, words in DEFAULT_KEYWORDS.items():
        for w in words:
            db.add(CareV1SosKeyword(category=category, keyword=w, enabled=True))
    await db.commit()


# ==================== Schemas ====================
class UiModeUpdate(BaseModel):
    ui_mode: str
    first_choice: Optional[bool] = None
    sos_floating_enabled: Optional[bool] = None


class SosDetectRequest(BaseModel):
    text: str


class SosCreateRequest(BaseModel):
    trigger_source: str
    trigger_keyword: Optional[str] = None
    trigger_text: Optional[str] = None
    location_lat: Optional[str] = None
    location_lng: Optional[str] = None


class SosResolveRequest(BaseModel):
    status: str  # cancelled / closed / dispatched_120 / dispatched_family
    countdown_remaining_ms: Optional[int] = None


class KeywordUpsert(BaseModel):
    category: str
    keyword: str
    enabled: bool = True


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
    pref.ui_mode_set_at = datetime.utcnow()
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


# ==================== SOS 关键词配置 ====================
@router.get("/api/care-v1/sos/keywords")
async def get_keywords(db: AsyncSession = Depends(get_db)):
    await ensure_default_keywords(db)
    result = await db.execute(
        select(CareV1SosKeyword).where(CareV1SosKeyword.enabled == True)  # noqa: E712
    )
    items = result.scalars().all()
    out: Dict[str, List[str]] = {"high_risk": [], "symptom": [], "degree": [], "negation": []}
    for it in items:
        if it.category in out:
            out[it.category].append(it.keyword)
    return {"code": 200, "data": out}


@router.post("/api/care-v1/admin/sos/keywords")
async def admin_add_keyword(
    body: KeywordUpsert,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if body.category not in ("high_risk", "symptom", "degree", "negation"):
        raise HTTPException(status_code=400, detail="无效的 category")
    existing = await db.execute(
        select(CareV1SosKeyword).where(
            CareV1SosKeyword.category == body.category,
            CareV1SosKeyword.keyword == body.keyword,
        )
    )
    item = existing.scalar_one_or_none()
    if item:
        item.enabled = body.enabled
        item.updated_by = current_user.id
    else:
        item = CareV1SosKeyword(
            category=body.category,
            keyword=body.keyword,
            enabled=body.enabled,
            updated_by=current_user.id,
        )
        db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"code": 200, "data": {"id": item.id}}


@router.delete("/api/care-v1/admin/sos/keywords/{kw_id}")
async def admin_delete_keyword(
    kw_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CareV1SosKeyword).where(CareV1SosKeyword.id == kw_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="关键词不存在")
    await db.delete(item)
    await db.commit()
    return {"code": 200, "data": {"deleted": kw_id}}


# ==================== SOS 触发检测 ====================
async def _load_keywords_map(db: AsyncSession) -> Dict[str, List[str]]:
    await ensure_default_keywords(db)
    result = await db.execute(
        select(CareV1SosKeyword).where(CareV1SosKeyword.enabled == True)  # noqa: E712
    )
    out: Dict[str, List[str]] = {"high_risk": [], "symptom": [], "degree": [], "negation": []}
    for it in result.scalars().all():
        if it.category in out:
            out[it.category].append(it.keyword)
    return out


_QUESTION_PATTERNS = ["?", "？", "是不是", "怎么办", "会不会", "对不对", "吗"]


def detect_sos_trigger(text: str, kws: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    返回 {"hit": bool, "rule": "high_risk"|"combo"|"none", "matched": [...], "reason": str}
    实现 PRD §6.3 三规则 + §6.4 三道防误报。
    """
    if not text or not text.strip():
        return {"hit": False, "rule": "none", "matched": [], "reason": "空文本"}

    # 防误报 2：疑问句过滤（优先于否定词，因为疑问句也常含"不"）
    for q in _QUESTION_PATTERNS:
        if q in text:
            return {"hit": False, "rule": "none", "matched": [], "reason": f"疑问句: {q}"}

    # 防误报 1：否定词过滤
    for neg in kws.get("negation", []):
        if neg and neg in text:
            return {"hit": False, "rule": "none", "matched": [], "reason": f"否定词命中: {neg}"}

    # 规则 1：高危词单触
    for kw in kws.get("high_risk", []):
        if kw in text:
            return {"hit": True, "rule": "high_risk", "matched": [kw], "reason": "高危词单触"}

    # 规则 2：症状词 + 程度词双触
    matched_symptom = [k for k in kws.get("symptom", []) if k in text]
    matched_degree = [k for k in kws.get("degree", []) if k in text]
    if matched_symptom and matched_degree:
        return {
            "hit": True,
            "rule": "combo",
            "matched": matched_symptom + matched_degree,
            "reason": "症状词+程度词双触",
        }

    # 规则 3：单独症状词 → 不推 SOS
    return {"hit": False, "rule": "none", "matched": matched_symptom, "reason": "无触发"}


@router.post("/api/care-v1/sos/detect")
async def sos_detect(body: SosDetectRequest, db: AsyncSession = Depends(get_db)):
    kws = await _load_keywords_map(db)
    result = detect_sos_trigger(body.text, kws)
    return {"code": 200, "data": result}


# ==================== SOS 事件 ====================
@router.post("/api/care-v1/sos/events")
async def create_sos_event(
    body: SosCreateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = CareV1SosEvent(
        user_id=current_user.id,
        trigger_source=body.trigger_source,
        trigger_keyword=body.trigger_keyword,
        trigger_text=body.trigger_text,
        status="pending",
        location_lat=body.location_lat,
        location_lng=body.location_lng,
        health_snapshot_json={
            "blood_pressure": "128/82 mmHg",
            "blood_glucose": "7.2 mmol/L",
            "heart_rate": "78 bpm",
            "note": "演示快照（实际从用户健康档案生成）",
        },
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"code": 200, "data": {"id": event.id, "status": event.status}}


@router.put("/api/care-v1/sos/events/{event_id}/resolve")
async def resolve_sos_event(
    event_id: int,
    body: SosResolveRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CareV1SosEvent).where(
            CareV1SosEvent.id == event_id, CareV1SosEvent.user_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="SOS 事件不存在")
    if body.status not in ("cancelled", "closed", "dispatched_120", "dispatched_family"):
        raise HTTPException(status_code=400, detail="无效的 status")
    event.status = body.status
    if body.countdown_remaining_ms is not None:
        event.countdown_remaining_ms = body.countdown_remaining_ms
    if body.status == "dispatched_120":
        event.call_120_at = datetime.utcnow()
    if body.status in ("closed", "cancelled"):
        event.resolved_at = datetime.utcnow()
    await db.commit()
    return {"code": 200, "data": {"id": event.id, "status": event.status}}


@router.get("/api/care-v1/sos/events")
async def list_sos_events(
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CareV1SosEvent)
        .where(CareV1SosEvent.user_id == current_user.id)
        .order_by(desc(CareV1SosEvent.created_at))
        .limit(limit)
    )
    items = result.scalars().all()
    return {
        "code": 200,
        "data": [
            {
                "id": it.id,
                "trigger_source": it.trigger_source,
                "trigger_keyword": it.trigger_keyword,
                "status": it.status,
                "created_at": it.created_at.isoformat() if it.created_at else None,
                "resolved_at": it.resolved_at.isoformat() if it.resolved_at else None,
            }
            for it in items
        ],
    }


# ==================== AI 主动卡片聚合 ====================
@router.get("/api/care-v1/home/proactive-cards")
async def get_proactive_cards(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回首屏四张卡片：健康简报（含血糖）、用药提醒、居家安全、SOS 关怀（条件触发）"""

    # 健康简报（演示数据；真实场景从 vital_measurements 聚合）
    latest_bp = {"systolic": 128, "diastolic": 82, "abnormal": False}
    latest_bg = {"value": 7.2, "unit": "mmol/L", "abnormal": True}  # >7.0 异常
    sleep = {"hours": 6.5, "abnormal": False}
    steps = {"value": 3240, "abnormal": False}

    # 用药提醒（演示数据）
    med_reminders = [
        {"name": "降压药", "schedule": "早上 8:00", "done": False},
        {"name": "降糖药", "schedule": "午饭后", "done": False},
    ]

    # 居家安全（演示数据 + 用户实际设备）
    device_result = await db.execute(
        select(CareV1UserDevice).where(CareV1UserDevice.user_id == current_user.id)
    )
    user_devices = device_result.scalars().all()
    if user_devices:
        devices_data = [
            {
                "type": d.device_type,
                "name": d.device_name or d.device_type,
                "status": d.status,
                "battery": d.battery_level or 0,
                "abnormal": d.status != "online" or (d.battery_level or 100) < 20,
            }
            for d in user_devices
        ]
    else:
        devices_data = [
            {"type": "emergency_caller", "name": "紧急呼叫器", "status": "online", "battery": 85, "abnormal": False},
            {"type": "smoke_detector", "name": "烟感报警器", "status": "online", "battery": 18, "abnormal": True},
        ]

    cards = {
        "health_brief": {
            "label": "健康简报 · 今日",
            "blood_pressure": latest_bp,
            "blood_glucose": latest_bg,
            "sleep": sleep,
            "steps": steps,
        },
        "med_reminder": {"label": "用药提醒", "items": med_reminders},
        "home_safety": {"label": "居家安全", "devices": devices_data},
        "sos_care": None,  # 仅触发时填充
    }
    return {"code": 200, "data": cards}


# ==================== 欢迎区（称呼 + 时段问候 + 关怀语） ====================
def _greeting_by_hour(hour: int) -> str:
    if 5 <= hour < 11:
        return "早上好 ☀️"
    if 11 <= hour < 13:
        return "中午好 🌤"
    if 13 <= hour < 18:
        return "下午好 ☀️"
    if 18 <= hour < 22:
        return "晚上好 🌙"
    return "夜深了 🌙"


@router.get("/api/care-v1/home/welcome")
async def get_welcome(
    current_user=Depends(get_current_user),
):
    nickname = getattr(current_user, "nickname", None) or getattr(current_user, "name", None) or "您好"
    now = datetime.now()
    greeting = _greeting_by_hour(now.hour)
    care_text = "今天血压记得测哦 ❤"
    return {
        "code": 200,
        "data": {
            "nickname": nickname,
            "greeting": greeting,
            "care_text": care_text,
            "main_text": f"{nickname}，{greeting}",
        },
    }
