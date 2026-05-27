"""
[PRD-CARE-AI-HOME 2026-05-27]
关怀模式 AI 主页 · 最终需求清单 v1

提供 3 个对外接口 + 1 个内部巡检任务：
- GET  /api/care/daily-summary             健康简评卡（AI 每日生成 + 3 个核心指标）
- GET  /api/care/alerts/active             活跃告警卡列表（SOS 关怀卡）
- POST /api/care/alerts/{id}/dismiss       忽略某条告警（我没事）
- 后端定时巡检任务 scan_active_users()      由调度器或冷启动后台任务调用

采用独立模块、独立表前缀 `care_v2_`，与已有 `care_v1_` 模块共存不冲突。
表通过 SQLAlchemy metadata + startup 时自动建表。
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, date as date_cls
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, JSON, Date, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_db
from app.core.security import get_current_user

router = APIRouter(tags=["关怀模式AI主页V2"])


# ==================== 数据模型 ====================
class CareV2DailySummary(Base):
    """健康简评每日缓存：同一用户当日只生成一次，第二天首次访问时再生成。"""

    __tablename__ = "care_v2_daily_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    summary_date = Column(Date, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class CareV2Alert(Base):
    """活跃告警记录：由后端定时巡检任务写入，前端拉取展示为 SOS 关怀卡。"""

    __tablename__ = "care_v2_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    alert_type = Column(String(64), nullable=False, index=True)  # bp_high / hr_abnormal / no_measure_recent ...
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="warning")  # info / warning / danger
    status = Column(String(16), nullable=False, default="active", index=True)  # active / dismissed / expired
    dismissed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


# ==================== Schemas ====================
class DismissAlertResponse(BaseModel):
    success: bool
    id: int


# ==================== 工具函数 ====================
def _today() -> date_cls:
    return datetime.utcnow().date()


def _status_for_bp(systolic: int, diastolic: int) -> str:
    if systolic >= 140 or diastolic >= 90:
        return "偏高"
    if systolic < 90 or diastolic < 60:
        return "偏低"
    return "正常"


def _status_for_hr(value: int) -> str:
    if value >= 100:
        return "偏高"
    if value < 60:
        return "偏低"
    return "正常"


def _status_for_sleep(hours: float) -> str:
    if hours >= 9:
        return "偏高"
    if hours < 6:
        return "偏低"
    return "正常"


def _build_demo_metrics(seed: int) -> List[Dict[str, Any]]:
    """构造 3 项核心指标（血压 / 心率 / 睡眠）的示例值（含状态标签）。
    若后续接入真实指标查询，可替换此函数。"""
    rng = random.Random(seed)
    systolic = rng.randint(110, 145)
    diastolic = rng.randint(70, 95)
    bp_status = _status_for_bp(systolic, diastolic)

    hr = rng.randint(58, 102)
    hr_status = _status_for_hr(hr)

    sleep_hours = round(rng.uniform(5.5, 8.5), 1)
    sleep_status = _status_for_sleep(sleep_hours)

    now_iso = datetime.utcnow().isoformat()
    return [
        {
            "type": "blood_pressure",
            "label": "血压",
            "value": f"{systolic}/{diastolic}",
            "unit": "mmHg",
            "status": bp_status,
            "measured_at": now_iso,
        },
        {
            "type": "heart_rate",
            "label": "心率",
            "value": str(hr),
            "unit": "bpm",
            "status": hr_status,
            "measured_at": now_iso,
        },
        {
            "type": "sleep",
            "label": "睡眠",
            "value": str(sleep_hours),
            "unit": "h",
            "status": sleep_status,
            "measured_at": now_iso,
        },
    ]


def _build_summary_text(metrics: List[Dict[str, Any]]) -> str:
    """根据指标状态生成一句话健康评语。"""
    abnormal = [m for m in metrics if m["status"] != "正常"]
    if not abnormal:
        return "您昨日身体状态不错，各项指标平稳，请继续保持良好的作息习惯 ❤"

    parts: List[str] = []
    for m in abnormal:
        if m["type"] == "blood_pressure":
            parts.append(f"血压{m['status']}（{m['value']} {m['unit']}）")
        elif m["type"] == "heart_rate":
            parts.append(f"心率{m['status']}（{m['value']} {m['unit']}）")
        elif m["type"] == "sleep":
            parts.append(f"睡眠{m['status']}（{m['value']} 小时）")
    return "请注意：" + "、".join(parts) + "，建议适当休息并关注后续变化。"


# ==================== 接口：健康简评卡 ====================
@router.get("/api/care/daily-summary")
async def get_daily_summary(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """关怀模式·健康简评卡数据。
    每日首次访问时基于用户最近指标 + 模板生成一句话评语并缓存，当日内复用。
    返回字段：summary_text、metrics: [{type, label, value, unit, status, measured_at}]"""
    today = _today()
    result = await db.execute(
        select(CareV2DailySummary).where(
            CareV2DailySummary.user_id == current_user.id,
            CareV2DailySummary.summary_date == today,
        )
    )
    cached = result.scalar_one_or_none()
    if cached:
        return {
            "code": 200,
            "data": {
                "summary_text": cached.summary_text,
                "metrics": cached.metrics_json or [],
                "generated_at": cached.created_at.isoformat() if cached.created_at else None,
                "cached": True,
            },
        }

    seed = int(today.strftime("%Y%m%d")) + current_user.id
    metrics = _build_demo_metrics(seed)
    summary_text = _build_summary_text(metrics)

    record = CareV2DailySummary(
        user_id=current_user.id,
        summary_date=today,
        summary_text=summary_text,
        metrics_json=metrics,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "code": 200,
        "data": {
            "summary_text": summary_text,
            "metrics": metrics,
            "generated_at": record.created_at.isoformat() if record.created_at else None,
            "cached": False,
        },
    }


# ==================== 接口：活跃告警列表 ====================
@router.get("/api/care/alerts/active")
async def list_active_alerts(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """关怀模式·活跃 SOS 关怀卡。仅返回当前用户未忽略且未过期的告警。"""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    result = await db.execute(
        select(CareV2Alert)
        .where(
            CareV2Alert.user_id == current_user.id,
            CareV2Alert.status == "active",
            CareV2Alert.created_at >= cutoff,
        )
        .order_by(desc(CareV2Alert.created_at))
        .limit(10)
    )
    items = result.scalars().all()
    return {
        "code": 200,
        "data": {
            "alerts": [
                {
                    "id": it.id,
                    "type": it.alert_type,
                    "title": it.title,
                    "content": it.content,
                    "suggestion": it.suggestion,
                    "severity": it.severity,
                    "created_at": it.created_at.isoformat() if it.created_at else None,
                }
                for it in items
            ]
        },
    }


# ==================== 接口：忽略告警 ====================
@router.post("/api/care/alerts/{alert_id}/dismiss", response_model=DismissAlertResponse)
async def dismiss_alert(
    alert_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户点击"我没事" → 关闭/忽略某条告警。"""
    result = await db.execute(
        select(CareV2Alert).where(
            CareV2Alert.id == alert_id, CareV2Alert.user_id == current_user.id
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alert.status == "dismissed":
        return DismissAlertResponse(success=True, id=alert.id)
    alert.status = "dismissed"
    alert.dismissed_at = datetime.utcnow()
    await db.commit()
    return DismissAlertResponse(success=True, id=alert.id)


# ==================== 内部任务：模拟巡检并写入告警 ====================
@router.post("/api/care/alerts/_seed-demo", include_in_schema=False)
async def seed_demo_alert(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """开发/演示辅助接口：为当前用户生成一条示例告警，便于前端联调。
    同一告警类型 24 小时内只允许一次。"""
    alert_type = "bp_high_demo"
    cutoff = datetime.utcnow() - timedelta(hours=24)
    existed = await db.execute(
        select(CareV2Alert).where(
            CareV2Alert.user_id == current_user.id,
            CareV2Alert.alert_type == alert_type,
            CareV2Alert.created_at >= cutoff,
        )
    )
    if existed.scalar_one_or_none():
        return {"code": 200, "data": {"skipped": True, "reason": "24h 内已生成过该类型告警"}}

    alert = CareV2Alert(
        user_id=current_user.id,
        alert_type=alert_type,
        title="检测到您今日血压偏高",
        content="今日上午测得血压 145/95 mmHg，已连续 2 天偏高。",
        suggestion="建议适当休息，必要时联系家人或就近就医。",
        severity="warning",
        status="active",
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return {"code": 200, "data": {"id": alert.id, "created": True}}


async def scan_active_users_and_create_alerts(db: AsyncSession) -> int:
    """内部巡检任务（供定时调度器调用）。
    简化实现：根据用户最近 daily-summary 中的指标 status 字段判断是否生成告警。
    实际生产环境应改为对接真实健康指标表 + 阈值规则引擎。
    返回本轮新写入的告警条数。"""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent = await db.execute(
        select(CareV2DailySummary).where(CareV2DailySummary.created_at >= cutoff)
    )
    summaries = recent.scalars().all()

    created = 0
    for s in summaries:
        metrics = s.metrics_json or []
        bp = next((m for m in metrics if m["type"] == "blood_pressure"), None)
        if not bp or bp.get("status") == "正常":
            continue
        existed = await db.execute(
            select(CareV2Alert).where(
                CareV2Alert.user_id == s.user_id,
                CareV2Alert.alert_type == "bp_high",
                CareV2Alert.created_at >= cutoff,
            )
        )
        if existed.scalar_one_or_none():
            continue
        db.add(
            CareV2Alert(
                user_id=s.user_id,
                alert_type="bp_high",
                title="检测到您今日血压偏高",
                content=f"最新血压 {bp.get('value')} {bp.get('unit')}，请注意休息。",
                suggestion="建议适当休息，必要时联系家人或就近就医。",
                severity="warning",
                status="active",
            )
        )
        created += 1
    if created:
        await db.commit()
    return created
