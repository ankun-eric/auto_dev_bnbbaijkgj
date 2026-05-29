"""[PRD-468 2026-05-12] 健康档案改版 v3 API。

接口前缀: /api/health-profile-v3

10 个端点：
- GET    /api/health-profile-v3/{profile_id}/today-metrics
- GET    /api/health-profile-v3/{profile_id}/metric/{metric_type}
- POST   /api/health-profile-v3/{profile_id}/metric/{metric_type}
- GET    /api/health-profile-v3/devices
- POST   /api/health-profile-v3/devices/{device_type}/bind
- POST   /api/health-profile-v3/devices/{device_type}/callback
- DELETE /api/health-profile-v3/devices/{device_type}
- POST   /api/health-profile-v3/devices/{device_type}/sync
- GET    /api/health-profile-v3/{profile_id}/medication-plan
- GET    /api/health-profile-v3/{profile_id}/events
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.health_v3 import DeviceBinding, HealthMetricRecord
from app.models.models import (
    HealthProfile,
    MedicationCheckIn,
    MedicationLog,
    MedicationPlan,
    MedicationReminder,
    User,
)
from app.schemas.health_v3 import (
    DeviceBindRequest,
    DeviceBindResponse,
    DeviceItem,
    DevicesListResponse,
    HealthEventItem,
    HealthEventsResponse,
    MedicationPlanCard,
    MedicationPlanResponse,
    MedicationProgressSnapshot,
    MedicationTimeChip,
    MetricCreateRequest,
    MetricHistoryResponse,
    MetricRecordOut,
    MetricSnapshot,
    TodayMetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health-profile-v3", tags=["PRD-468 健康档案改版"])

# 异常判定阈值（默认值）
THRESHOLDS = {
    "blood_pressure": {"systolic_max": 140, "diastolic_max": 90},
    "blood_glucose_fasting_max": 7.0,
    "blood_glucose_postprandial_max": 11.1,
    "heart_rate": {"min": 50, "max": 100},
    "sleep_hours_min": 6.0,
    "spo2_min": 95,
}

METRIC_TYPES = {"blood_pressure", "blood_glucose", "heart_rate", "sleep", "spo2"}


# ─── 设备字典 ────────────────────────────────────────────────────────────
DEVICE_CATALOG = [
    {"device_type": "huawei_watch", "name": "华为 Watch / GT 系列", "active": True},
    {"device_type": "xiaomi_band", "name": "小米手环 / Watch", "active": True},
    {"device_type": "glucometer", "name": "血糖仪（敬请期待）", "active": False},
    {"device_type": "bp_meter", "name": "血压计（敬请期待）", "active": False},
    {"device_type": "scale", "name": "体重秤（敬请期待）", "active": False},
]


# ─── 工具函数 ────────────────────────────────────────────────────────────

async def _verify_profile_access(
    db: AsyncSession, profile_id: int, user: User
) -> HealthProfile:
    """校验当前用户对该 profile_id 的访问权限。"""
    res = await db.execute(select(HealthProfile).where(HealthProfile.id == profile_id))
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")
    if profile.user_id != user.id:
        # 简化：本期仅校验所有者；共管访问下版本扩展
        raise HTTPException(status_code=403, detail="无权访问该档案")
    return profile


def _is_abnormal(metric_type: str, value: Dict[str, Any]) -> bool:
    if not value:
        return False
    try:
        if metric_type == "blood_pressure":
            sys = float(value.get("systolic") or 0)
            dia = float(value.get("diastolic") or 0)
            return sys > THRESHOLDS["blood_pressure"]["systolic_max"] or dia > THRESHOLDS["blood_pressure"]["diastolic_max"]
        if metric_type == "blood_glucose":
            v = float(value.get("value") or 0)
            period = (value.get("period") or "").lower()
            if "fasting" in period or "空腹" in (value.get("period") or ""):
                return v > THRESHOLDS["blood_glucose_fasting_max"]
            return v > THRESHOLDS["blood_glucose_postprandial_max"]
        if metric_type == "heart_rate":
            v = float(value.get("value") or 0)
            return v < THRESHOLDS["heart_rate"]["min"] or v > THRESHOLDS["heart_rate"]["max"]
        if metric_type == "sleep":
            v = float(value.get("duration_h") or 0)
            return v < THRESHOLDS["sleep_hours_min"]
        if metric_type == "spo2":
            v = float(value.get("value") or 0)
            return v < THRESHOLDS["spo2_min"]
    except Exception:
        return False
    return False


def _principal_value(metric_type: str, value: Dict[str, Any]) -> Optional[float]:
    """从 value_json 抽取一个主要数值用于趋势曲线。"""
    if not value:
        return None
    try:
        if metric_type == "blood_pressure":
            return float(value.get("systolic") or 0) or None
        if metric_type in ("blood_glucose", "heart_rate", "spo2"):
            return float(value.get("value") or 0) or None
        if metric_type == "sleep":
            return float(value.get("duration_h") or 0) or None
    except Exception:
        return None
    return None


def _schedule_of(reminder: "MedicationReminder") -> List[str]:
    """统一从 MedicationReminder 抽取每日服药时间点列表。

    [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 用药数据源统一到 MedicationReminder。
    优先使用 custom_times（JSON 数组），否则用 remind_time（单时间点），最后用 "08:00" 兜底。
    """
    if reminder.custom_times and isinstance(reminder.custom_times, list):
        out: List[str] = []
        for t in reminder.custom_times:
            if isinstance(t, str) and len(t) >= 4:
                out.append(t)
        if out:
            return out
    if reminder.remind_time:
        return [reminder.remind_time]
    return ["08:00"]


async def _list_active_reminders(
    db: AsyncSession, user_id: int, today: date
) -> List["MedicationReminder"]:
    """[BUG-HEALTH-ARCHIVE-V2 2026-05-16] 「在用药品」统一口径

    在用药品 = MedicationReminder WHERE
        user_id = current_user
        AND status = 'active'
        AND (long_term = True OR end_date IS NULL OR end_date >= TODAY)

    不再校验 start_date，允许预排未来开始的药也计入"在管理"。
    """
    from sqlalchemy import or_

    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    ).order_by(MedicationReminder.remind_time.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_latest_metric(
    db: AsyncSession, profile_id: int, metric_type: str
) -> Optional[HealthMetricRecord]:
    res = await db.execute(
        select(HealthMetricRecord)
        .where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
        )
        .order_by(HealthMetricRecord.measured_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


# ─── 今日指标 ────────────────────────────────────────────────────────────

@router.get("/{profile_id}/today-metrics", response_model=TodayMetricsResponse)
async def get_today_metrics(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_profile_access(db, profile_id, current_user)

    snapshots: Dict[str, MetricSnapshot] = {}
    for metric_type in METRIC_TYPES:
        latest = await _get_latest_metric(db, profile_id, metric_type)
        if latest:
            snapshots[metric_type] = MetricSnapshot(
                metric_type=metric_type,
                value=latest.value_json,
                measured_at=latest.measured_at.isoformat() if latest.measured_at else None,
                source=latest.source,
                is_abnormal=_is_abnormal(metric_type, latest.value_json or {}),
            )
        else:
            snapshots[metric_type] = MetricSnapshot(metric_type=metric_type)

    # 用药打卡进度（统一数据源到 MedicationReminder —— BUG-HEALTH-ARCHIVE-V2 2026-05-16）
    today = date.today()
    reminders = await _list_active_reminders(db, current_user.id, today)
    total_slots = sum(len(_schedule_of(r)) for r in reminders)
    checked_count = 0
    has_overdue = False
    now = datetime.utcnow()
    if reminders:
        reminder_ids = [r.id for r in reminders]
        checkin_stmt = select(MedicationCheckIn).where(
            MedicationCheckIn.reminder_id.in_(reminder_ids),
            MedicationCheckIn.check_in_date == today,
        )
        checkins = (await db.execute(checkin_stmt)).scalars().all()
        # MedicationCheckIn 不区分时间点（只记日打卡），全部时间点视为已打卡或未打卡
        checked_reminder_ids = {c.reminder_id for c in checkins}
        for r in reminders:
            schedule = _schedule_of(r)
            if r.id in checked_reminder_ids:
                checked_count += len(schedule)
        # 检测是否有逾期：reminder 当前任一时间点 + 15min 已过且未打卡
        for r in reminders:
            if r.id in checked_reminder_ids:
                continue
            for t in _schedule_of(r):
                try:
                    h, m = int(t[:2]), int(t[3:])
                    sched_dt = datetime.combine(today, datetime.min.time()).replace(hour=h, minute=m)
                    if now >= sched_dt + timedelta(minutes=15):
                        has_overdue = True
                        break
                except Exception:
                    continue
            if has_overdue:
                break

    return TodayMetricsResponse(
        profile_id=profile_id,
        blood_pressure=snapshots["blood_pressure"],
        blood_glucose=snapshots["blood_glucose"],
        heart_rate=snapshots["heart_rate"],
        sleep=snapshots["sleep"],
        spo2=snapshots["spo2"],
        medication=MedicationProgressSnapshot(
            checked=checked_count, total=total_slots, has_overdue=has_overdue,
        ),
    )


# ─── 单指标历史 / 录入 ────────────────────────────────────────────────────

@router.get("/{profile_id}/metric/{metric_type}", response_model=MetricHistoryResponse)
async def get_metric_history(
    profile_id: int,
    metric_type: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if metric_type not in METRIC_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 metric_type: {metric_type}")
    await _verify_profile_access(db, profile_id, current_user)

    # 7 天趋势
    today = date.today()
    trend_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    trend_stmt = (
        select(HealthMetricRecord)
        .where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
            HealthMetricRecord.measured_at >= trend_start,
        )
        .order_by(HealthMetricRecord.measured_at.asc())
    )
    trend_records = (await db.execute(trend_stmt)).scalars().all()
    by_day: Dict[str, List[float]] = {}
    # 血压专用 sbp/dbp 双数列
    sbp_by_day: Dict[str, List[float]] = {}
    dbp_by_day: Dict[str, List[float]] = {}
    for r in trend_records:
        key = r.measured_at.strftime("%Y-%m-%d")
        vjson = r.value_json or {}
        v = _principal_value(metric_type, vjson)
        if v is not None:
            by_day.setdefault(key, []).append(v)
        if metric_type == "blood_pressure":
            sbp = vjson.get("systolic")
            dbp = vjson.get("diastolic")
            try:
                if sbp is not None:
                    sbp_by_day.setdefault(key, []).append(float(sbp))
            except (TypeError, ValueError):
                pass
            try:
                if dbp is not None:
                    dbp_by_day.setdefault(key, []).append(float(dbp))
            except (TypeError, ValueError):
                pass

    trend_7days: List[Optional[float]] = []
    trend_dates: List[str] = []
    trend_day_labels: List[str] = []
    trend_systolic: List[Optional[float]] = []
    trend_diastolic: List[Optional[float]] = []
    # 周几标签（周一~周日），最后一天用"今日"
    _CN_WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i in range(7):
        d = today - timedelta(days=6 - i)
        ds = d.strftime("%Y-%m-%d")
        trend_dates.append(ds)
        trend_day_labels.append("今日" if i == 6 else _CN_WEEK[d.weekday()])
        vals = by_day.get(ds)
        trend_7days.append(round(sum(vals) / len(vals), 2) if vals else None)
        if metric_type == "blood_pressure":
            svals = sbp_by_day.get(ds)
            dvals = dbp_by_day.get(ds)
            trend_systolic.append(round(sum(svals) / len(svals), 2) if svals else None)
            trend_diastolic.append(round(sum(dvals) / len(dvals), 2) if dvals else None)

    # 历史分页
    total_stmt = select(func.count(HealthMetricRecord.id)).where(
        HealthMetricRecord.profile_id == profile_id,
        HealthMetricRecord.metric_type == metric_type,
    )
    total = (await db.execute(total_stmt)).scalar() or 0

    list_stmt = (
        select(HealthMetricRecord)
        .where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
        )
        .order_by(HealthMetricRecord.measured_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(list_stmt)).scalars().all()
    records = [
        MetricRecordOut(
            id=r.id,
            profile_id=r.profile_id,
            metric_type=r.metric_type,
            value=r.value_json or {},
            source=r.source,
            measured_at=r.measured_at,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return MetricHistoryResponse(
        metric_type=metric_type,
        trend_7days=trend_7days,
        records=records,
        total=int(total),
        trend_dates=trend_dates,
        trend_day_labels=trend_day_labels,
        trend_systolic=trend_systolic,
        trend_diastolic=trend_diastolic,
    )


@router.post("/{profile_id}/metric/{metric_type}", response_model=MetricRecordOut)
async def create_metric(
    profile_id: int,
    metric_type: str,
    body: MetricCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if metric_type not in METRIC_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 metric_type: {metric_type}")
    await _verify_profile_access(db, profile_id, current_user)

    measured_at = body.measured_at or datetime.utcnow()
    record = HealthMetricRecord(
        profile_id=profile_id,
        metric_type=metric_type,
        value_json=body.value,
        source=body.source or "manual",
        measured_at=measured_at,
        created_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # [PRD-HEALTH-DASHBOARD-V1] 体征录入后自动触发异常检查 + 复查提醒取消
    if metric_type in ("blood_pressure", "blood_glucose", "heart_rate"):
        try:
            from app.services.health_dashboard_service import (
                cancel_recheck_if_data_recorded,
                check_and_alert,
            )
            profile = await _verify_profile_access(db, profile_id, current_user)
            member_id = profile.family_member_id
            if member_id:
                await cancel_recheck_if_data_recorded(db, member_id, metric_type)
                await check_and_alert(db, member_id, metric_type)
                await db.commit()
        except Exception:
            logger.warning("health dashboard alert check failed after metric create", exc_info=True)

    return MetricRecordOut(
        id=record.id,
        profile_id=record.profile_id,
        metric_type=record.metric_type,
        value=record.value_json or {},
        source=record.source,
        measured_at=record.measured_at,
        created_at=record.created_at,
    )


# ─── 设备绑定 ────────────────────────────────────────────────────────────

@router.get("/devices", response_model=DevicesListResponse)
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(DeviceBinding).where(DeviceBinding.user_id == current_user.id)
    )
    bindings_map = {b.device_type: b for b in res.scalars().all()}
    items: List[DeviceItem] = []
    for d in DEVICE_CATALOG:
        binding = bindings_map.get(d["device_type"])
        if not d["active"]:
            status = "coming_soon"
        elif binding and binding.status == "active":
            status = "active"
        else:
            status = "unbound"
        items.append(DeviceItem(
            id=binding.id if binding else None,
            device_type=d["device_type"],
            name=d["name"],
            status=status,
            last_sync_at=binding.last_sync_at if binding else None,
        ))
    return DevicesListResponse(items=items)


@router.post("/devices/{device_type}/bind", response_model=DeviceBindResponse)
async def bind_device(
    device_type: str,
    body: DeviceBindRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    catalog = {d["device_type"]: d for d in DEVICE_CATALOG}
    if device_type not in catalog:
        raise HTTPException(status_code=400, detail="未知 device_type")
    if not catalog[device_type]["active"]:
        return DeviceBindResponse(bound=False, message="敬请期待")

    # 本期最小版本：直接占位绑定（无真实 OAuth）。后续切真接平台 OAuth。
    existing = (await db.execute(
        select(DeviceBinding).where(
            DeviceBinding.user_id == current_user.id,
            DeviceBinding.device_type == device_type,
        )
    )).scalar_one_or_none()
    device_id = body.device_id or f"mock-{device_type}-{current_user.id}"
    if existing:
        existing.status = "active"
        existing.device_id = device_id
        existing.bound_at = datetime.utcnow()
    else:
        db.add(DeviceBinding(
            user_id=current_user.id,
            device_type=device_type,
            device_id=device_id,
            status="active",
            bound_at=datetime.utcnow(),
        ))
    await db.commit()
    return DeviceBindResponse(bound=True, message="设备已绑定（占位通道，等待平台 Key 切真接）")


@router.post("/devices/{device_type}/callback", response_model=DeviceBindResponse)
async def device_callback(
    device_type: str,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # OAuth 回调本期仅占位接收，后续接入华为/小米平台时实现。
    return DeviceBindResponse(bound=True, message="OAuth 回调占位完成")


@router.delete("/devices/{device_type}")
async def unbind_device(
    device_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(DeviceBinding).where(
            DeviceBinding.user_id == current_user.id,
            DeviceBinding.device_type == device_type,
        )
    )
    binding = res.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="设备未绑定")
    binding.status = "unbound"
    await db.commit()
    return {"ok": True}


@router.post("/devices/{device_type}/sync")
async def sync_device(
    device_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(DeviceBinding).where(
            DeviceBinding.user_id == current_user.id,
            DeviceBinding.device_type == device_type,
            DeviceBinding.status == "active",
        )
    )
    binding = res.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="设备未绑定")
    binding.last_sync_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "last_sync_at": binding.last_sync_at.isoformat()}


# ─── 用药计划 ────────────────────────────────────────────────────────────

@router.get("/{profile_id}/medication-plan", response_model=MedicationPlanResponse)
async def get_medication_plan(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 健康档案用药计划 Tab 数据源
    统一切到 MedicationReminder（health-plan-v2），废弃 MedicationPlan 读取。

    口径：「在用药品」 = status='active' AND (long_term=True OR end_date IS NULL OR end_date >= TODAY)
    """
    await _verify_profile_access(db, profile_id, current_user)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # 周一
    reminders = await _list_active_reminders(db, current_user.id, today)

    items: List[MedicationPlanCard] = []
    for r in reminders:
        schedule = _schedule_of(r)
        # 今日打卡状态：MedicationCheckIn 不区分时间点，按日打卡
        checkin_q = await db.execute(
            select(MedicationCheckIn).where(
                MedicationCheckIn.reminder_id == r.id,
                MedicationCheckIn.check_in_date == today,
            )
        )
        checked_today_all = checkin_q.scalar_one_or_none() is not None
        chips = [
            MedicationTimeChip(scheduled_time=t, checked=checked_today_all)
            for t in schedule
        ]

        # 本周完成率：本周内 reminder 的打卡天数 × 每日时间点数 / (本周已过天数 × 每日时间点数)
        weekly_q = await db.execute(
            select(func.count(MedicationCheckIn.id)).where(
                MedicationCheckIn.reminder_id == r.id,
                MedicationCheckIn.check_in_date >= week_start,
                MedicationCheckIn.check_in_date <= today,
            )
        )
        weekly_days_checked = int(weekly_q.scalar() or 0)
        slots_per_day = max(len(schedule), 1)
        weekly_completed = weekly_days_checked * slots_per_day
        days_so_far = (today - week_start).days + 1
        weekly_total = slots_per_day * days_so_far
        rate = round(weekly_completed / weekly_total * 100, 1) if weekly_total else 0.0
        # 防止溢出 100%
        if rate > 100.0:
            rate = 100.0
            weekly_completed = weekly_total

        items.append(MedicationPlanCard(
            plan_id=r.id,
            drug_name=r.medicine_name,
            dosage=r.dosage or "",
            schedule=schedule,
            time_chips=chips,
            weekly_completed=weekly_completed,
            weekly_total=weekly_total,
            weekly_rate=rate,
        ))

    return MedicationPlanResponse(items=items)


# ─── 健康事件流（最小可用：从指标记录 + 用药日志聚合） ───────────────────

@router.get("/{profile_id}/events", response_model=HealthEventsResponse)
async def list_events(
    profile_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_profile_access(db, profile_id, current_user)

    # 简化版：聚合最近指标录入事件
    res = await db.execute(
        select(HealthMetricRecord)
        .where(HealthMetricRecord.profile_id == profile_id)
        .order_by(HealthMetricRecord.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = res.scalars().all()
    type_label = {
        "blood_pressure": "血压",
        "blood_glucose": "血糖",
        "heart_rate": "心率",
        "sleep": "睡眠",
        "spo2": "血氧",
    }
    items = [
        HealthEventItem(
            id=r.id,
            type="metric_record",
            title=f"录入「{type_label.get(r.metric_type, r.metric_type)}」数据",
            detail=str(r.value_json),
            occurred_at=r.created_at,
        )
        for r in rows
    ]
    total_q = await db.execute(
        select(func.count(HealthMetricRecord.id)).where(HealthMetricRecord.profile_id == profile_id)
    )
    total = int(total_q.scalar() or 0)
    return HealthEventsResponse(items=items, page=page, size=size, total=total)
