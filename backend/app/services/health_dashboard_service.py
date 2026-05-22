"""[PRD-HEALTH-DASHBOARD-V1] 家人健康看板 - 核心服务层。

包含：
- 权限校验（守护者/拥有者）
- 健康评分计算（血压25%+血糖25%+心率15%+用药20%+录入规律性15%）
- 最新体征数据聚合
- 今日事件汇总
- 用药完成度汇总
- 体检摘要
- 趋势数据查询
- 异常检测 + 复查提醒自动创建 + 守护者通知
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_v3 import HealthMetricRecord
from app.models.models import (
    CheckupReport,
    FamilyManagement,
    FamilyMember,
    HealthAlertNotification,
    HealthProfile,
    HealthReminder,
    MedicationCheckIn,
    MedicationReminder,
    Notification,
    NotificationType,
    SystemMessage,
    User,
)

logger = logging.getLogger(__name__)

# ─── 异常阈值（系统默认，不可修改） ────────────────────────────────────
ABNORMAL_THRESHOLDS = {
    "blood_pressure": {
        "systolic_high": 140, "systolic_low": 90,
        "diastolic_high": 90, "diastolic_low": 60,
    },
    "blood_sugar": {
        "fasting_high": 7.0, "fasting_low": 3.9,
        "postprandial_high": 11.1,
    },
    "heart_rate": {"high": 100, "low": 50},
}

# 正常范围（前端展示用）
NORMAL_RANGES = {
    "blood_pressure": {"systolic": [90, 139], "diastolic": [60, 89]},
    "blood_sugar": {"fasting": [3.9, 6.1], "postprandial": [0, 7.8]},
    "heart_rate": [60, 100],
}

MAX_DAILY_ALERTS_PER_METRIC = 3


# ─── 权限校验 ──────────────────────────────────────────────────────────

async def verify_member_access(db: AsyncSession, member_id: int, user_id: int) -> FamilyMember:
    """校验当前用户是否为该 member 的拥有者或守护者。"""
    res = await db.execute(select(FamilyMember).where(FamilyMember.id == member_id))
    member = res.scalar_one_or_none()
    if not member:
        return None

    if member.user_id == user_id:
        return member
    if member.member_user_id and member.member_user_id == user_id:
        return member

    fm = (
        await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.managed_member_id == member_id,
                or_(
                    FamilyManagement.manager_user_id == user_id,
                    FamilyManagement.managed_user_id == user_id,
                ),
                FamilyManagement.status == "active",
            )
        )
    ).scalar_one_or_none()
    if fm is not None:
        return member
    return None


async def _get_profile_for_member(db: AsyncSession, member: FamilyMember) -> Optional[HealthProfile]:
    """获取家庭成员关联的 HealthProfile。"""
    res = await db.execute(
        select(HealthProfile).where(HealthProfile.family_member_id == member.id)
    )
    profile = res.scalar_one_or_none()
    if not profile:
        res = await db.execute(
            select(HealthProfile).where(HealthProfile.user_id == member.user_id)
        )
        profile = res.scalar_one_or_none()
    return profile


# ─── 异常判定 ──────────────────────────────────────────────────────────

def is_blood_pressure_abnormal(systolic: float, diastolic: float) -> bool:
    t = ABNORMAL_THRESHOLDS["blood_pressure"]
    return (systolic >= t["systolic_high"] or systolic < t["systolic_low"]
            or diastolic >= t["diastolic_high"] or diastolic < t["diastolic_low"])


def is_blood_sugar_abnormal(value: float, period: str = "fasting") -> bool:
    t = ABNORMAL_THRESHOLDS["blood_sugar"]
    if "fasting" in period.lower() or "空腹" in period:
        return value >= t["fasting_high"] or value < t["fasting_low"]
    return value >= t["postprandial_high"]


def is_heart_rate_abnormal(value: float) -> bool:
    t = ABNORMAL_THRESHOLDS["heart_rate"]
    return value > t["high"] or value < t["low"]


def check_metric_abnormal(metric_type: str, value_json: dict) -> bool:
    if not value_json:
        return False
    try:
        if metric_type == "blood_pressure":
            sys_val = float(value_json.get("systolic") or 0)
            dia_val = float(value_json.get("diastolic") or 0)
            return is_blood_pressure_abnormal(sys_val, dia_val)
        if metric_type == "blood_glucose":
            val = float(value_json.get("value") or 0)
            period = value_json.get("period", "fasting")
            return is_blood_sugar_abnormal(val, period)
        if metric_type == "heart_rate":
            val = float(value_json.get("value") or 0)
            return is_heart_rate_abnormal(val)
    except (TypeError, ValueError):
        pass
    return False


def _format_metric_value(metric_type: str, value_json: dict) -> str:
    if metric_type == "blood_pressure":
        return f"{value_json.get('systolic', 0)}/{value_json.get('diastolic', 0)}"
    if metric_type in ("blood_glucose", "heart_rate"):
        return str(value_json.get("value", 0))
    return str(value_json)


# ─── 健康评分计算 ──────────────────────────────────────────────────────

async def calculate_health_score(
    db: AsyncSession,
    profile: HealthProfile,
    member: FamilyMember,
) -> Tuple[float, Dict[str, float]]:
    """健康评分满分100：血压(25)+血糖(25)+心率(15)+用药完成度(20)+录入规律性(15)"""
    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    bp_score = 25.0
    bs_score = 25.0
    hr_score = 15.0
    med_score = 0.0
    reg_score = 0.0

    if profile:
        # Blood pressure score (25 points)
        bp_records = await _get_recent_metrics(db, profile.id, "blood_pressure", 7)
        if bp_records:
            abnormal_count = sum(1 for r in bp_records if check_metric_abnormal("blood_pressure", r.value_json))
            ratio = 1 - (abnormal_count / len(bp_records))
            bp_score = round(25 * ratio, 1)
        else:
            bp_score = 0

        # Blood sugar score (25 points)
        bs_records = await _get_recent_metrics(db, profile.id, "blood_glucose", 7)
        if bs_records:
            abnormal_count = sum(1 for r in bs_records if check_metric_abnormal("blood_glucose", r.value_json))
            ratio = 1 - (abnormal_count / len(bs_records))
            bs_score = round(25 * ratio, 1)
        else:
            bs_score = 0

        # Heart rate score (15 points)
        hr_records = await _get_recent_metrics(db, profile.id, "heart_rate", 7)
        if hr_records:
            abnormal_count = sum(1 for r in hr_records if check_metric_abnormal("heart_rate", r.value_json))
            ratio = 1 - (abnormal_count / len(hr_records))
            hr_score = round(15 * ratio, 1)
        else:
            hr_score = 0

        # Medication completion (20 points)
        med_score = await _calculate_medication_score(db, member, today)

        # Recording regularity (15 points)
        reg_score = await _calculate_regularity_score(db, profile.id, seven_days_ago, today)

    total = bp_score + bs_score + hr_score + med_score + reg_score
    return round(total, 1), {
        "blood_pressure_score": bp_score,
        "blood_sugar_score": bs_score,
        "heart_rate_score": hr_score,
        "medication_score": med_score,
        "regularity_score": reg_score,
    }


async def _get_recent_metrics(
    db: AsyncSession, profile_id: int, metric_type: str, days: int
) -> list:
    since = datetime.utcnow() - timedelta(days=days)
    res = await db.execute(
        select(HealthMetricRecord).where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
            HealthMetricRecord.measured_at >= since,
        ).order_by(HealthMetricRecord.measured_at.desc())
    )
    return list(res.scalars().all())


async def _calculate_medication_score(db: AsyncSession, member: FamilyMember, today: date) -> float:
    """用药完成度评分（满分20分），基于近7天打卡率"""
    user_id = member.user_id
    seven_days_ago = today - timedelta(days=7)

    reminders_stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= seven_days_ago,
        ),
    )
    # Also filter by family_member_id if reminders are per-member
    if hasattr(MedicationReminder, "family_member_id"):
        reminders_stmt = reminders_stmt.where(
            or_(
                MedicationReminder.family_member_id == member.id,
                MedicationReminder.family_member_id.is_(None),
            )
        )

    res = await db.execute(reminders_stmt)
    reminders = list(res.scalars().all())

    if not reminders:
        return 20.0  # no medications = full score

    total_slots = 0
    checked_slots = 0
    reminder_ids = [r.id for r in reminders]

    for d in range(7):
        check_date = today - timedelta(days=d)
        for r in reminders:
            schedule = _schedule_of(r)
            total_slots += len(schedule)

    checkins = (
        await db.execute(
            select(MedicationCheckIn).where(
                MedicationCheckIn.reminder_id.in_(reminder_ids),
                MedicationCheckIn.check_in_date >= seven_days_ago,
                MedicationCheckIn.check_in_date <= today,
            )
        )
    ).scalars().all()

    checkin_set = {(c.reminder_id, c.check_in_date) for c in checkins}
    for d in range(7):
        check_date = today - timedelta(days=d)
        for r in reminders:
            if (r.id, check_date) in checkin_set:
                checked_slots += len(_schedule_of(r))

    if total_slots == 0:
        return 20.0
    rate = checked_slots / total_slots
    return round(20 * rate, 1)


def _schedule_of(reminder: MedicationReminder) -> list:
    if reminder.custom_times and isinstance(reminder.custom_times, list):
        out = [t for t in reminder.custom_times if isinstance(t, str) and len(t) >= 4]
        if out:
            return out
    if reminder.remind_time:
        return [reminder.remind_time]
    return ["08:00"]


async def _calculate_regularity_score(
    db: AsyncSession, profile_id: int, since: date, until: date
) -> float:
    """录入规律性评分（满分15分）：7天内有记录的天数/7"""
    res = await db.execute(
        select(func.date(HealthMetricRecord.measured_at))
        .where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.measured_at >= datetime.combine(since, datetime.min.time()),
            HealthMetricRecord.measured_at <= datetime.combine(until, datetime.max.time()),
        )
        .group_by(func.date(HealthMetricRecord.measured_at))
    )
    days_with_records = len(res.all())
    total_days = (until - since).days or 1
    ratio = min(days_with_records / total_days, 1.0)
    return round(15 * ratio, 1)


# ─── 最新体征 ──────────────────────────────────────────────────────────

async def get_latest_vitals(db: AsyncSession, profile_id: int) -> dict:
    result = {}
    for metric_type in ("blood_pressure", "blood_glucose", "heart_rate"):
        res = await db.execute(
            select(HealthMetricRecord)
            .where(
                HealthMetricRecord.profile_id == profile_id,
                HealthMetricRecord.metric_type == metric_type,
            )
            .order_by(HealthMetricRecord.measured_at.desc())
            .limit(1)
        )
        record = res.scalar_one_or_none()
        if record and record.value_json:
            vj = record.value_json
            recorded_at = record.measured_at.isoformat() if record.measured_at else None
            abnormal = check_metric_abnormal(metric_type, vj)

            if metric_type == "blood_pressure":
                result["blood_pressure"] = {
                    "systolic": vj.get("systolic"),
                    "diastolic": vj.get("diastolic"),
                    "is_abnormal": abnormal,
                    "recorded_at": recorded_at,
                }
            elif metric_type == "blood_glucose":
                result["blood_sugar"] = {
                    "fasting": vj.get("value") if "fasting" in (vj.get("period") or "").lower() else None,
                    "postprandial": vj.get("value") if "postprandial" in (vj.get("period") or "").lower() else None,
                    "is_abnormal": abnormal,
                    "recorded_at": recorded_at,
                }
            elif metric_type == "heart_rate":
                result["heart_rate"] = {
                    "value": vj.get("value"),
                    "is_abnormal": abnormal,
                    "recorded_at": recorded_at,
                }
        else:
            key = "blood_sugar" if metric_type == "blood_glucose" else metric_type
            result[key] = None
    return result


# ─── 今日事件 ──────────────────────────────────────────────────────────

async def get_today_events(
    db: AsyncSession, profile_id: int, member: FamilyMember, today: date
) -> list:
    events = []

    # Vital sign records from today
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    res = await db.execute(
        select(HealthMetricRecord).where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.measured_at >= today_start,
            HealthMetricRecord.measured_at <= today_end,
        ).order_by(HealthMetricRecord.measured_at.asc())
    )
    for r in res.scalars():
        vj = r.value_json or {}
        time_str = r.measured_at.strftime("%H:%M") if r.measured_at else "00:00"
        abnormal = check_metric_abnormal(r.metric_type, vj)
        if r.metric_type == "blood_pressure":
            title = f"血压 {vj.get('systolic', '-')}/{vj.get('diastolic', '-')}"
        elif r.metric_type == "blood_glucose":
            title = f"血糖 {vj.get('value', '-')}"
        elif r.metric_type == "heart_rate":
            title = f"心率 {vj.get('value', '-')}"
        else:
            title = f"{r.metric_type} 记录"
        events.append({
            "time": time_str,
            "type": "vital_sign",
            "title": title,
            "is_abnormal": abnormal,
        })

    # Medication events
    user_id = member.user_id
    rem_stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    )
    if hasattr(MedicationReminder, "family_member_id"):
        rem_stmt = rem_stmt.where(
            or_(
                MedicationReminder.family_member_id == member.id,
                MedicationReminder.family_member_id.is_(None),
            )
        )
    reminders = (await db.execute(rem_stmt)).scalars().all()

    reminder_ids = [r.id for r in reminders]
    checked_ids = set()
    if reminder_ids:
        checkins = (
            await db.execute(
                select(MedicationCheckIn).where(
                    MedicationCheckIn.reminder_id.in_(reminder_ids),
                    MedicationCheckIn.check_in_date == today,
                )
            )
        ).scalars().all()
        checked_ids = {c.reminder_id for c in checkins}

    for r in reminders:
        for t in _schedule_of(r):
            events.append({
                "time": t,
                "type": "medication",
                "title": f"服用{r.medicine_name}",
                "completed": r.id in checked_ids,
            })

    events.sort(key=lambda e: e["time"])
    return events


# ─── 用药汇总 ──────────────────────────────────────────────────────────

def _time_to_period(time_str: str) -> str:
    """将时间 HH:MM 映射到用药时段"""
    try:
        h = int(time_str[:2])
    except (ValueError, IndexError):
        return "morning"
    if h < 11:
        return "morning"
    if h < 14:
        return "noon"
    if h < 20:
        return "evening"
    return "bedtime"


PERIOD_LABELS = {"morning": "早", "noon": "中", "evening": "晚", "bedtime": "睡前"}


async def get_medication_summary(db: AsyncSession, member: FamilyMember, today: date) -> dict:
    user_id = member.user_id
    rem_stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    )
    if hasattr(MedicationReminder, "family_member_id"):
        rem_stmt = rem_stmt.where(
            or_(
                MedicationReminder.family_member_id == member.id,
                MedicationReminder.family_member_id.is_(None),
            )
        )
    reminders = (await db.execute(rem_stmt)).scalars().all()

    reminder_ids = [r.id for r in reminders]
    checked_ids = set()
    if reminder_ids:
        checkins = (
            await db.execute(
                select(MedicationCheckIn).where(
                    MedicationCheckIn.reminder_id.in_(reminder_ids),
                    MedicationCheckIn.check_in_date == today,
                )
            )
        ).scalars().all()
        checked_ids = {c.reminder_id for c in checkins}

    periods = {p: [] for p in ("morning", "noon", "evening", "bedtime")}
    total_items = 0
    completed_items = 0

    for r in reminders:
        completed = r.id in checked_ids
        for t in _schedule_of(r):
            period = _time_to_period(t)
            periods[period].append({"name": r.medicine_name, "completed": completed})
            total_items += 1
            if completed:
                completed_items += 1

    rate = round((completed_items / total_items * 100) if total_items > 0 else 0, 1)

    return {
        "completion_rate": rate,
        "periods": [
            {"period": p, "label": PERIOD_LABELS[p], "items": periods[p]}
            for p in ("morning", "noon", "evening", "bedtime")
        ],
    }


# ─── 体检摘要 ──────────────────────────────────────────────────────────

async def get_checkup_summary(db: AsyncSession, member: FamilyMember) -> dict:
    today = date.today()
    res = await db.execute(
        select(CheckupReport)
        .where(
            CheckupReport.family_member_id == member.id,
            CheckupReport.status != "deleted",
        )
        .order_by(CheckupReport.report_date.desc())
        .limit(1)
    )
    latest = res.scalar_one_or_none()

    abnormal_items = []
    latest_date = None

    if latest:
        latest_date = latest.report_date.isoformat() if latest.report_date else None
        if latest.ai_analysis_json and isinstance(latest.ai_analysis_json, dict):
            items = latest.ai_analysis_json.get("abnormal_items") or []
            abnormal_items = [str(i) for i in items[:10]]
        elif latest.indicators and isinstance(latest.indicators, list):
            for ind in latest.indicators:
                if isinstance(ind, dict) and ind.get("is_abnormal"):
                    abnormal_items.append(ind.get("name", "未知"))

    # Next checkup / followup from HealthReminder
    next_checkup_days = None
    next_followup_days = None

    checkup_res = await db.execute(
        select(HealthReminder).where(
            HealthReminder.member_id == member.id,
            HealthReminder.reminder_type == "checkup",
            HealthReminder.status == "pending",
            HealthReminder.scheduled_date >= today,
        ).order_by(HealthReminder.scheduled_date.asc()).limit(1)
    )
    checkup_reminder = checkup_res.scalar_one_or_none()
    if checkup_reminder:
        next_checkup_days = (checkup_reminder.scheduled_date - today).days

    followup_res = await db.execute(
        select(HealthReminder).where(
            HealthReminder.member_id == member.id,
            HealthReminder.reminder_type.in_(["followup", "recheck"]),
            HealthReminder.status == "pending",
            HealthReminder.scheduled_date >= today,
        ).order_by(HealthReminder.scheduled_date.asc()).limit(1)
    )
    followup_reminder = followup_res.scalar_one_or_none()
    if followup_reminder:
        next_followup_days = (followup_reminder.scheduled_date - today).days

    return {
        "latest_date": latest_date,
        "abnormal_items": abnormal_items,
        "next_checkup_days": next_checkup_days,
        "next_followup_days": next_followup_days,
    }


# ─── 趋势数据 ──────────────────────────────────────────────────────────

async def get_trends(
    db: AsyncSession, profile_id: int, days: int = 7, metric: Optional[str] = None
) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    result: Dict[str, list] = {}

    metric_map = {
        "blood_pressure": "blood_pressure",
        "blood_sugar": "blood_glucose",
        "heart_rate": "heart_rate",
    }

    targets = metric_map.keys() if not metric else [metric]

    for m in targets:
        db_metric = metric_map.get(m, m)
        records = await db.execute(
            select(HealthMetricRecord).where(
                HealthMetricRecord.profile_id == profile_id,
                HealthMetricRecord.metric_type == db_metric,
                HealthMetricRecord.measured_at >= since,
            ).order_by(HealthMetricRecord.measured_at.asc())
        )

        items = []
        for r in records.scalars():
            vj = r.value_json or {}
            d = r.measured_at.strftime("%Y-%m-%d") if r.measured_at else ""
            abnormal = check_metric_abnormal(db_metric, vj)

            if m == "blood_pressure":
                items.append({
                    "date": d,
                    "systolic": vj.get("systolic"),
                    "diastolic": vj.get("diastolic"),
                    "is_abnormal": abnormal,
                })
            elif m == "blood_sugar":
                period = (vj.get("period") or "").lower()
                items.append({
                    "date": d,
                    "fasting": vj.get("value") if "fasting" in period else None,
                    "postprandial": vj.get("value") if "postprandial" in period else None,
                    "is_abnormal": abnormal,
                })
            elif m == "heart_rate":
                items.append({
                    "date": d,
                    "value": vj.get("value"),
                    "is_abnormal": abnormal,
                })

        result[m] = items

    return result


# ─── 异常检查 + 复查提醒 + 守护者通知 ─────────────────────────────────

async def check_and_alert(
    db: AsyncSession,
    member_id: int,
    metric_type: Optional[str] = None,
) -> dict:
    """检查最新体征数据是否异常，异常时：
    1. 创建 HealthAlertNotification
    2. 创建 3 天后复查提醒（如3天内已有则跳过）
    3. 通知守护者
    """
    member_res = await db.execute(select(FamilyMember).where(FamilyMember.id == member_id))
    member = member_res.scalar_one_or_none()
    if not member:
        return {"checked": True, "abnormal_found": False, "alerts_created": 0, "recheck_reminders_created": 0, "details": []}

    profile = await _get_profile_for_member(db, member)
    if not profile:
        return {"checked": True, "abnormal_found": False, "alerts_created": 0, "recheck_reminders_created": 0, "details": []}

    check_types = [metric_type] if metric_type else ["blood_pressure", "blood_glucose", "heart_rate"]
    alerts_created = 0
    recheck_created = 0
    details = []
    abnormal_found = False
    today = date.today()
    now = datetime.utcnow()

    for mt in check_types:
        res = await db.execute(
            select(HealthMetricRecord)
            .where(
                HealthMetricRecord.profile_id == profile.id,
                HealthMetricRecord.metric_type == mt,
            )
            .order_by(HealthMetricRecord.measured_at.desc())
            .limit(1)
        )
        record = res.scalar_one_or_none()
        if not record or not record.value_json:
            continue

        is_abn = check_metric_abnormal(mt, record.value_json)
        if not is_abn:
            continue

        abnormal_found = True
        metric_display = {"blood_pressure": "血压", "blood_glucose": "血糖", "heart_rate": "心率"}.get(mt, mt)
        metric_value_str = _format_metric_value(mt, record.value_json)
        response_key = "blood_sugar" if mt == "blood_glucose" else mt

        # Get guardians
        guardians = await _get_guardians(db, member)

        for gid in guardians:
            # Check daily limit
            today_alert_count = await _count_today_alerts(db, member_id, gid, mt, today)
            if today_alert_count >= MAX_DAILY_ALERTS_PER_METRIC:
                continue

            alert = HealthAlertNotification(
                member_id=member_id,
                guardian_user_id=gid,
                metric_type=mt,
                metric_value=metric_value_str,
                is_abnormal=True,
                notification_channel="app",
                delivery_status="sent",
                sent_at=now,
            )
            db.add(alert)

            # Send in-app notification
            notification = Notification(
                user_id=gid,
                title=f"{member.nickname or '家人'}{metric_display}异常",
                content=f"{member.nickname or '家人'}的{metric_display}指标异常（{metric_value_str}），请关注。",
                type=NotificationType.health,
            )
            db.add(notification)

            alerts_created += 1

        # Create recheck reminder (3 days later), skip if one exists within 3 days
        recheck_date = today + timedelta(days=3)
        existing_recheck = await db.execute(
            select(HealthReminder).where(
                HealthReminder.member_id == member_id,
                HealthReminder.reminder_type == "recheck",
                HealthReminder.related_metric == mt,
                HealthReminder.status == "pending",
                HealthReminder.scheduled_date <= recheck_date,
                HealthReminder.scheduled_date >= today,
            )
        )
        if not existing_recheck.scalar_one_or_none():
            recheck = HealthReminder(
                user_id=member.user_id,
                member_id=member_id,
                reminder_type="recheck",
                title=f"{metric_display}复查",
                scheduled_date=recheck_date,
                status="pending",
                source="system_recheck",
                related_metric=mt,
                created_by=member.user_id,
            )
            db.add(recheck)
            recheck_created += 1

        details.append({
            "metric_type": response_key,
            "metric_value": metric_value_str,
            "is_abnormal": True,
            "alerts_sent": alerts_created,
        })

    await db.flush()
    return {
        "checked": True,
        "abnormal_found": abnormal_found,
        "alerts_created": alerts_created,
        "recheck_reminders_created": recheck_created,
        "details": details,
    }


async def _get_guardians(db: AsyncSession, member: FamilyMember) -> set:
    """复用守护者集合算法"""
    from app.services.family_guardian_service import guardians_of
    return await guardians_of(db, member)


async def _count_today_alerts(
    db: AsyncSession, member_id: int, guardian_user_id: int, metric_type: str, today: date
) -> int:
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    res = await db.execute(
        select(func.count(HealthAlertNotification.id)).where(
            HealthAlertNotification.member_id == member_id,
            HealthAlertNotification.guardian_user_id == guardian_user_id,
            HealthAlertNotification.metric_type == metric_type,
            HealthAlertNotification.created_at >= today_start,
            HealthAlertNotification.created_at <= today_end,
        )
    )
    return res.scalar() or 0


# ─── 复查提醒自动取消 ─────────────────────────────────────────────────

async def cancel_recheck_if_data_recorded(
    db: AsyncSession,
    member_id: int,
    metric_type: str,
):
    """录入新数据后，如果3天内有pending的系统复查提醒则自动取消"""
    today = date.today()
    three_days_later = today + timedelta(days=3)

    res = await db.execute(
        select(HealthReminder).where(
            HealthReminder.member_id == member_id,
            HealthReminder.reminder_type == "recheck",
            HealthReminder.related_metric == metric_type,
            HealthReminder.source == "system_recheck",
            HealthReminder.status == "pending",
            HealthReminder.scheduled_date >= today,
            HealthReminder.scheduled_date <= three_days_later,
        )
    )
    for reminder in res.scalars():
        reminder.status = "cancelled"
        logger.info("Auto-cancelled recheck reminder %d for member %d metric %s", reminder.id, member_id, metric_type)

    await db.flush()


# ─── 体检推荐 ──────────────────────────────────────────────────────────

def get_checkup_recommendations(member: FamilyMember, latest_checkup_date: Optional[date] = None) -> dict:
    """根据年龄推荐体检频率"""
    today = date.today()
    age = 0
    if member.birthday:
        age = today.year - member.birthday.year
        if (today.month, today.day) < (member.birthday.month, member.birthday.day):
            age -= 1

    if age < 40:
        freq = "每两年一次"
        interval = 24
        age_group = "40岁以下"
        suggestions = ["基础体检套餐", "常规血液检查", "视力听力检查"]
    elif age < 60:
        freq = "每年一次"
        interval = 12
        age_group = "40-60岁"
        suggestions = ["全面体检套餐", "心脑血管专项", "肿瘤标志物筛查", "骨密度检查"]
    else:
        freq = "每半年一次"
        interval = 6
        age_group = "60岁以上"
        suggestions = ["老年体检套餐", "心脑血管专项", "肿瘤标志物筛查", "骨密度检查", "认知功能评估", "跌倒风险评估"]

    days_since = None
    next_date = None
    if latest_checkup_date:
        days_since = (today - latest_checkup_date).days
        next_date = (latest_checkup_date + timedelta(days=interval * 30)).isoformat()

    return {
        "recommended_frequency": freq,
        "recommended_interval_months": interval,
        "last_checkup_date": latest_checkup_date.isoformat() if latest_checkup_date else None,
        "days_since_last_checkup": days_since,
        "next_recommended_date": next_date,
        "age_group": age_group,
        "suggestions": suggestions,
    }
