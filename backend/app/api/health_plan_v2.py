import json
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    HealthCheckInItem,
    HealthCheckInRecord,
    HealthProfile,
    MedicationCheckIn,
    MedicationReminder,
    PlanTemplateCategory,
    RecommendedPlan,
    RecommendedPlanTask,
    ReminderSetting,
    User,
    UserPlan,
    UserPlanTask,
    UserPlanTaskRecord,
)
from app.schemas.health_plan_v2 import (
    AIGenerateCategoryPlanRequest,
    AIGeneratePlanV2Request,
    CheckInStatisticsResponse,
    HealthCheckInItemCreate,
    HealthCheckInItemResponse,
    HealthCheckInItemUpdate,
    HealthCheckInRecordCreate,
    HealthCheckInRecordResponse,
    MedicationReminderCreate,
    MedicationReminderResponse,
    MedicationReminderUpdate,
    PlanRanking,
    PlanTemplateCategoryResponse,
    QuickCheckInRequest,
    RecommendedPlanResponse,
    RecommendedPlanTaskResponse,
    TodayTodoGroup,
    TodayTodoItem,
    TodayTodoResponse,
    UserPlanCreate,
    UserPlanResponse,
    UserPlanTaskCheckInCreate,
    UserPlanTaskResponse,
    UserPlanUpdate,
)
from app.services.ai_service import call_ai_model

router = APIRouter(prefix="/api/health-plan", tags=["健康计划V2"])


# ──────────────── 用药提醒 ────────────────


def _norm_drug_name(name: Optional[str]) -> str:
    """[PRD-MED-PLAN-V1] 同名药品判定：去前后空白 + 大小写不敏感（中文不受影响）。"""
    return (name or "").strip().lower()


async def _find_active_same_name(
    db: AsyncSession, user_id: int, drug_name: str, exclude_id: Optional[int] = None
) -> Optional[MedicationReminder]:
    """查询当前用户是否已有同名「进行中」用药计划。"""
    today = date.today()
    target = _norm_drug_name(drug_name)
    if not target:
        return None
    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
    )
    res = await db.execute(stmt)
    for r in res.scalars().all():
        if exclude_id and r.id == exclude_id:
            continue
        # 仅判定「进行中」：未结束（长期 OR end_date IS NULL OR end_date >= today）
        is_ongoing = bool(r.long_term) or r.end_date is None or (r.end_date and r.end_date >= today)
        if is_ongoing and _norm_drug_name(r.medicine_name) == target:
            return r
    return None


def _compute_end_date(start_date: Optional[date], duration_days: Optional[int]) -> Optional[date]:
    """[PRD-MED-PLAN-V1] 服用周期 = 开始日期 + 服用天数 - 1。"""
    if start_date is None or duration_days is None or duration_days <= 0:
        return None
    return start_date + timedelta(days=duration_days - 1)


# [PRD-MED-PLAN-OPTIM-V1 2026-05-17 R-09] 服用时机老枚举 → 新枚举映射兜底
_TIMING_LEGACY_MAP = {
    "早上": "饭前",
    "中午": "饭后",
    "下午": "饭后",
    "晚上": "饭后",
    "睡前": "睡前",
    "morning": "饭前",
    "noon": "饭后",
    "afternoon": "饭后",
    "evening": "饭后",
    "bedtime": "睡前",
}
_TIMING_VALID = {"饭前", "饭后", "空腹", "随餐", "睡前"}


def _migrate_timing(raw: Optional[str]) -> Optional[str]:
    """读时兜底：将服用时机老枚举映射到新枚举（饭前/饭后/空腹/随餐/睡前）。"""
    if not raw:
        return raw
    if raw in _TIMING_VALID:
        return raw
    return _TIMING_LEGACY_MAP.get(raw, raw)


# ──────────────── [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 批量查询药品是否已加入用药计划 ────────────────


@router.get("/medications/check-batch")
async def check_medications_batch(
    drug_names: str = Query(..., description="逗号分隔的药品名列表"),
    consultant_id: Optional[int] = Query(None, description="咨询人(family_member)ID，省略或0=本人"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-AI-DRUG-CARD-MEDPLAN-V1] 批量查询识药卡片药名是否已加入当前咨询人有效期内的用药计划。

    匹配规则：
    - 当前用户 user_id = current_user.id
    - family_member_id = consultant_id（None / 0 / 空 视为「本人」即 family_member_id IS NULL）
    - status = 'active'
    - 用药周期覆盖今天：long_term=True OR end_date IS NULL OR end_date >= today
      并且 start_date IS NULL OR start_date <= today
    - 字段：medicine_name OR generic_name 任一 LIKE %drug_name% （宽松匹配，大小写不敏感）

    返回：{ "code": 0, "data": { "药名": true/false, ... } }
    """
    names_raw = [n.strip() for n in (drug_names or "").split(",") if n.strip()]
    if not names_raw:
        return {"code": 0, "data": {}}

    today_d = date.today()
    conds = [
        MedicationReminder.user_id == current_user.id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today_d,
        ),
        or_(
            MedicationReminder.start_date.is_(None),
            MedicationReminder.start_date <= today_d,
        ),
    ]
    if consultant_id and consultant_id > 0:
        conds.append(MedicationReminder.family_member_id == consultant_id)
    else:
        conds.append(MedicationReminder.family_member_id.is_(None))

    res = await db.execute(
        select(
            MedicationReminder.medicine_name,
            MedicationReminder.generic_name,
        ).where(and_(*conds))
    )
    rows = res.all()

    pool: list[tuple[str, str]] = []
    for mn, gn in rows:
        pool.append(((mn or "").lower(), (gn or "").lower()))

    result: dict[str, bool] = {}
    for raw in names_raw:
        key = raw.lower()
        hit = False
        if key:
            for mn, gn in pool:
                if (mn and key in mn) or (gn and key in gn) or (mn and mn in key) or (gn and gn in key):
                    hit = True
                    break
        result[raw] = hit
    return {"code": 0, "data": result}


@router.post("/medications", response_model=MedicationReminderResponse)
async def create_medication(
    data: MedicationReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = data.model_dump(exclude_unset=True)
    drug_name = payload.get("medicine_name") or ""

    # [PRD-MED-PLAN-OPTIM-V1 R-09] 服用时机老枚举入参兜底迁移
    if "guidance" in payload:
        payload["guidance"] = _migrate_timing(payload.get("guidance"))

    # [PRD-MED-PLAN-V1] 同名药品去重：不允许同时存在两条「进行中」
    existing = await _find_active_same_name(db, current_user.id, drug_name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MEDICATION_DUPLICATE_ACTIVE",
                "message": f"您已有一条进行中的【{existing.medicine_name}】用药计划",
                "existing_id": existing.id,
                "existing_name": existing.medicine_name,
            },
        )

    # [PRD-MED-PLAN-V1] 服用周期自动计算 end_date
    start_d = payload.get("start_date")
    duration = payload.get("duration_days")
    if payload.get("long_term"):
        # [PRD-MED-PLAN-OPTIM-V1 R-03] 长期服用时 end_date 必须为 null
        payload["end_date"] = None
    else:
        if start_d and duration and not payload.get("end_date"):
            payload["end_date"] = _compute_end_date(start_d, duration)
        # 默认开始日期 = 今天，默认天数 = 5
        if start_d is None:
            payload["start_date"] = date.today()
        if duration is None and not payload.get("end_date"):
            payload["duration_days"] = 5
            payload["end_date"] = _compute_end_date(payload["start_date"], 5)

    reminder = MedicationReminder(
        user_id=current_user.id,
        **{k: v for k, v in payload.items() if k != "user_id"},
    )
    db.add(reminder)
    await db.flush()
    await db.refresh(reminder)
    resp = MedicationReminderResponse.model_validate(reminder)
    resp.today_checked = False
    return resp


@router.get("/medications")
async def list_medications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationReminder)
        .where(MedicationReminder.user_id == current_user.id, MedicationReminder.status == "active")
        .order_by(MedicationReminder.remind_time.asc())
    )
    reminders = result.scalars().all()

    today = date.today()
    checkin_result = await db.execute(
        select(MedicationCheckIn.reminder_id).where(
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == today,
        )
    )
    checked_ids = {row[0] for row in checkin_result.all()}

    groups: dict = {}
    for r in reminders:
        resp = MedicationReminderResponse.model_validate(r)
        resp.today_checked = r.id in checked_ids
        period = r.time_period or "其他"
        groups.setdefault(period, []).append(resp)

    return {"groups": groups, "total": len(reminders)}


# ──────────────── [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 统一用药数据源 ────────────────


def _active_med_filter(user_id: int, today: date):
    """构造「在用药品」过滤条件：

    在用药品 = MedicationReminder WHERE
        user_id = current_user
        AND status = 'active'
        AND (long_term = True OR end_date IS NULL OR end_date >= TODAY)
    """
    return [
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    ]


def _schedule_from_reminder(r: MedicationReminder) -> list[str]:
    """从 MedicationReminder 抽取每日服药时间点列表（兼容 MedicationPlan.schedule[]）。"""
    if r.custom_times and isinstance(r.custom_times, list):
        out: list[str] = []
        for t in r.custom_times:
            if isinstance(t, str) and len(t) >= 4:
                out.append(t)
        if out:
            return out
    if r.remind_time:
        return [r.remind_time]
    return ["08:00"]


async def _auto_archive_expired(db: AsyncSession, user_id: int) -> int:
    """[PRD-MED-PLAN-V1] 服用周期到期自动归档：status=active 且 end_date < today 且 非长期 → status=archived"""
    today = date.today()
    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        MedicationReminder.long_term != True,  # noqa: E712
        MedicationReminder.end_date.is_not(None),
        MedicationReminder.end_date < today,
    )
    expired = (await db.execute(stmt)).scalars().all()
    for r in expired:
        r.status = "archived"
    if expired:
        await db.flush()
    return len(expired)


async def _read_med_ai_call_enabled(db: AsyncSession, user_id: int) -> bool:
    """读取「用药 AI 外呼提醒」全局开关；不存在则视为关闭。"""
    res = await db.execute(
        select(ReminderSetting).where(ReminderSetting.user_id == user_id)
    )
    s = res.scalar_one_or_none()
    if s is None:
        return False
    return bool(getattr(s, "medication_ai_call_enabled", False) or False)


@router.get("/medications/list")
async def list_medications_flat(
    segment: Optional[str] = Query(None, description="筛选: today=今日用药 / all=全部在用药品 / archived=历史用药 / 空=全部在用药品"),
    tab: Optional[str] = Query(None, description="[PRD-MED-PLAN-ENTRY-V1] Tab 过滤: in_progress/not_started/finished；空=in_progress（与 segment 二选一，segment 优先）"),
    consultant_id: Optional[int] = Query(None, description="[PRD-AI-DRUG-CARD-MEDPLAN-V1] 咨询人(family_member)ID过滤；None/0=本人(family_member_id IS NULL)；-1=不过滤"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUG-HEALTH-ARCHIVE-V2 2026-05-16 / PRD-MED-PLAN-V1 2026-05-16] 用药计划列表。

    - 进入接口时自动归档已过期的「进行中」计划。
    - 透出全局开关 ai_call_enabled，前端用于控制电话图标 + 引导横幅。
    """
    today = date.today()

    # [PRD-MED-PLAN-V1] 自动归档（每次列表请求执行一次，幂等）
    await _auto_archive_expired(db, current_user.id)

    ai_call_enabled = await _read_med_ai_call_enabled(db, current_user.id)

    if segment == "archived":
        stmt = select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status.in_(["archived", "deleted"]),
        ).order_by(MedicationReminder.end_date.desc().nullslast(), MedicationReminder.id.desc())
    elif tab == "not_started":
        # [PRD-MED-PLAN-ENTRY-V1] 未开始：start_date > today 且 status != deleted
        stmt = select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status != "deleted",
            MedicationReminder.start_date.is_not(None),
            MedicationReminder.start_date > today,
        ).order_by(MedicationReminder.created_at.desc())
    elif tab == "finished":
        # [PRD-MED-PLAN-ENTRY-V1] 已结束：(status=archived) 或 (end_date < today 且非 long_term)
        stmt = select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status != "deleted",
            or_(
                MedicationReminder.status == "archived",
                and_(
                    MedicationReminder.end_date.is_not(None),
                    MedicationReminder.end_date < today,
                    MedicationReminder.long_term != True,  # noqa: E712
                ),
            ),
        ).order_by(MedicationReminder.end_date.desc().nullslast(), MedicationReminder.created_at.desc())
    elif tab == "in_progress":
        # [PRD-MED-PLAN-ENTRY-V1] 服药中：active + 已开始 + 未结束
        stmt = select(MedicationReminder).where(
            *_active_med_filter(current_user.id, today),
            or_(
                MedicationReminder.long_term == True,  # noqa: E712
                MedicationReminder.start_date.is_(None),
                MedicationReminder.start_date <= today,
            ),
        ).order_by(MedicationReminder.created_at.desc())
    else:
        # 兼容旧行为：未传 tab/segment 时返回全部「在用药品」（含未到 start_date 的）
        stmt = select(MedicationReminder).where(*_active_med_filter(current_user.id, today)).order_by(
            MedicationReminder.remind_time.asc()
        )

    # [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 咨询人过滤：
    #   - None：不过滤（兼容旧客户端）
    #   - -1 ：明确不过滤
    #   - 0  ：本人 → family_member_id IS NULL
    #   - >0 ：指定家庭成员
    if consultant_id is not None and consultant_id != -1:
        if consultant_id == 0:
            stmt = stmt.where(MedicationReminder.family_member_id.is_(None))
        else:
            stmt = stmt.where(MedicationReminder.family_member_id == consultant_id)

    reminders = (await db.execute(stmt)).scalars().all()

    items: list[dict] = []
    for r in reminders:
        schedule = _schedule_from_reminder(r)
        is_today = bool(schedule)
        if segment == "today" and not is_today:
            continue
        freq_per_day = r.frequency_per_day or len(schedule) or 1
        is_ongoing = (
            r.status == "active"
            and (
                bool(r.long_term)
                or r.end_date is None
                or (r.end_date and r.end_date >= today)
            )
        )
        # AI 外呼开 + 进行中 → 列表卡片显示电话图标
        ai_call_badge = bool(ai_call_enabled and is_ongoing)
        items.append({
            "id": r.id,
            "drug_name": r.medicine_name,
            "medicine_name": r.medicine_name,
            "dosage": r.dosage or "",
            "frequency": f"每日 {freq_per_day} 次",
            "frequency_per_day": freq_per_day,
            "schedule": schedule,
            "remind_time": r.remind_time,
            "time_period": r.time_period,
            "custom_times": r.custom_times,
            "long_term": bool(r.long_term),
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "duration_days": r.duration_days,
            "status": r.status,
            "enabled": (r.status == "active") and bool(r.reminder_enabled if r.reminder_enabled is not None else True),
            "note": r.notes,
            "notes": r.notes,
            "disease_tags": r.disease_tags or [],
            "reminder_enabled": bool(r.reminder_enabled if r.reminder_enabled is not None else True),
            "patient_id": None,
            # [PRD-MED-PLAN-V1] 新结构化字段
            "dosage_value": r.dosage_value,
            "dosage_unit": r.dosage_unit,
            # [PRD-MED-PLAN-OPTIM-V1 R-09] 服用时机读时兜底
            "guidance": _migrate_timing(r.guidance),
            # [PRD-MED-PLAN-V1] 标记：列表卡片是否显示电话图标
            "ai_call_badge": ai_call_badge,
            "is_ongoing": is_ongoing,
            # [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 咨询人归属 + 通用名
            "family_member_id": r.family_member_id,
            "generic_name": r.generic_name,
        })

    return {
        "items": items,
        "total": len(items),
        # [PRD-MED-PLAN-V1] 全局开关，前端用于引导横幅 / 电话图标
        "ai_call_enabled": ai_call_enabled,
    }


@router.get("/medications/summary")
async def get_medication_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUG-HEALTH-ARCHIVE-V2 2026-05-16] 「在用药品」摘要计数 —— 供 Hero 第 4 格使用。"""
    today = date.today()
    stmt = select(func.count(MedicationReminder.id)).where(
        *_active_med_filter(current_user.id, today)
    )
    count = int((await db.execute(stmt)).scalar() or 0)
    return {
        "active_count": count,
        "label": "在用药品",
        "unit": "种",
    }


@router.get("/medications/{reminder_id}", response_model=MedicationReminderResponse)
async def get_medication_detail(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="用药提醒不存在")
    # [PRD-MED-PLAN-OPTIM-V1 R-09] 服用时机读时兜底
    resp = MedicationReminderResponse.model_validate(reminder)
    resp.guidance = _migrate_timing(resp.guidance)
    today = date.today()
    checkin_result = await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.reminder_id == reminder_id,
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == today,
        )
    )
    resp.today_checked = checkin_result.scalar_one_or_none() is not None
    return resp


@router.put("/medications/{reminder_id}", response_model=MedicationReminderResponse)
async def update_medication(
    reminder_id: int,
    data: MedicationReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="用药提醒不存在")

    payload = data.model_dump(exclude_unset=True)
    # [PRD-MED-PLAN-OPTIM-V1 R-09] 服用时机老枚举入参兜底迁移
    if "guidance" in payload:
        payload["guidance"] = _migrate_timing(payload.get("guidance"))
    # [PRD-MED-PLAN-V1] 改名时要做同名「进行中」去重（排除自身）
    if "medicine_name" in payload and payload["medicine_name"]:
        existing = await _find_active_same_name(
            db, current_user.id, payload["medicine_name"], exclude_id=reminder.id
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "MEDICATION_DUPLICATE_ACTIVE",
                    "message": f"您已有一条进行中的【{existing.medicine_name}】用药计划",
                    "existing_id": existing.id,
                    "existing_name": existing.medicine_name,
                },
            )

    for field, value in payload.items():
        setattr(reminder, field, value)

    # [PRD-MED-PLAN-OPTIM-V1 R-03] long_term=True 时强制清空 end_date
    if reminder.long_term:
        reminder.end_date = None
    else:
        # [PRD-MED-PLAN-V1] 周期重算
        sd = reminder.start_date
        dd = reminder.duration_days
        if sd and dd and ("duration_days" in payload or "start_date" in payload):
            reminder.end_date = _compute_end_date(sd, dd)

    await db.flush()
    await db.refresh(reminder)
    resp = MedicationReminderResponse.model_validate(reminder)
    resp.guidance = _migrate_timing(resp.guidance)
    return resp


@router.delete("/medications/{reminder_id}")
async def delete_medication(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="用药提醒不存在")
    reminder.status = "deleted"
    await db.flush()
    return {"message": "删除成功"}


@router.put("/medications/{reminder_id}/pause")
async def toggle_pause_medication(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="用药提醒不存在")
    reminder.is_paused = not reminder.is_paused
    await db.flush()
    return {"message": "操作成功", "is_paused": reminder.is_paused}


@router.post("/medications/{reminder_id}/checkin")
async def checkin_medication(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status == "active",
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="用药提醒不存在")

    today = date.today()
    existing = await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.reminder_id == reminder_id,
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == today,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="今日已打卡")

    checkin = MedicationCheckIn(
        reminder_id=reminder_id,
        user_id=current_user.id,
        check_in_date=today,
        check_in_time=datetime.utcnow(),
    )
    db.add(checkin)
    points_result = {"points_earned": 0, "points_limit_reached": False}
    try:
        from app.services.checkin_points_service import award_checkin_points
        points_result = await award_checkin_points(db, current_user, "用药提醒打卡")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"打卡积分发放异常: {e}")
    await db.flush()
    return {"message": "打卡成功", "points_earned": points_result["points_earned"], "points_limit_reached": points_result["points_limit_reached"]}


# ──────────────── 健康打卡 ────────────────


@router.post("/checkin-items", response_model=HealthCheckInItemResponse)
async def create_checkin_item(
    data: HealthCheckInItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = HealthCheckInItem(
        user_id=current_user.id,
        name=data.name,
        target_value=data.target_value,
        target_unit=data.target_unit,
        remind_times=data.remind_times,
        repeat_frequency=data.repeat_frequency or "daily",
        custom_days=data.custom_days,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    resp = HealthCheckInItemResponse.model_validate(item)
    resp.today_completed = False
    return resp


@router.get("/checkin-items")
async def list_checkin_items(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheckInItem)
        .where(HealthCheckInItem.user_id == current_user.id, HealthCheckInItem.status == "active")
        .order_by(HealthCheckInItem.created_at.asc())
    )
    items = result.scalars().all()

    today = date.today()
    record_result = await db.execute(
        select(HealthCheckInRecord.item_id).where(
            HealthCheckInRecord.user_id == current_user.id,
            HealthCheckInRecord.check_in_date == today,
            HealthCheckInRecord.is_completed == True,
        )
    )
    completed_ids = {row[0] for row in record_result.all()}

    resp_items = []
    for item in items:
        resp = HealthCheckInItemResponse.model_validate(item)
        resp.today_completed = item.id in completed_ids
        resp_items.append(resp)

    return {"items": resp_items, "total": len(resp_items)}


@router.get("/checkin-items/{item_id}", response_model=HealthCheckInItemResponse)
async def get_checkin_item_detail(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.id == item_id,
            HealthCheckInItem.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="打卡项不存在")
    resp = HealthCheckInItemResponse.model_validate(item)
    today = date.today()
    record_result = await db.execute(
        select(HealthCheckInRecord).where(
            HealthCheckInRecord.item_id == item_id,
            HealthCheckInRecord.user_id == current_user.id,
            HealthCheckInRecord.check_in_date == today,
            HealthCheckInRecord.is_completed == True,
        )
    )
    resp.today_completed = record_result.scalar_one_or_none() is not None
    return resp


@router.put("/checkin-items/{item_id}", response_model=HealthCheckInItemResponse)
async def update_checkin_item(
    item_id: int,
    data: HealthCheckInItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.id == item_id,
            HealthCheckInItem.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="打卡项不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    await db.refresh(item)
    return HealthCheckInItemResponse.model_validate(item)


@router.delete("/checkin-items/{item_id}")
async def delete_checkin_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.id == item_id,
            HealthCheckInItem.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="打卡项不存在")
    item.status = "deleted"
    await db.flush()
    return {"message": "删除成功"}


@router.post("/checkin-items/{item_id}/checkin")
async def checkin_health_item(
    item_id: int,
    data: HealthCheckInRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.id == item_id,
            HealthCheckInItem.user_id == current_user.id,
            HealthCheckInItem.status == "active",
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="打卡项不存在")

    today = date.today()
    existing = await db.execute(
        select(HealthCheckInRecord).where(
            HealthCheckInRecord.item_id == item_id,
            HealthCheckInRecord.user_id == current_user.id,
            HealthCheckInRecord.check_in_date == today,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="今日已打卡")

    record = HealthCheckInRecord(
        item_id=item_id,
        user_id=current_user.id,
        check_in_date=today,
        actual_value=data.actual_value,
        is_completed=True,
        check_in_time=datetime.utcnow(),
    )
    db.add(record)
    points_result = {"points_earned": 0, "points_limit_reached": False}
    try:
        from app.services.checkin_points_service import award_checkin_points
        points_result = await award_checkin_points(db, current_user, "健康习惯打卡")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"打卡积分发放异常: {e}")
    await db.flush()
    return {"message": "打卡成功", "points_earned": points_result["points_earned"], "points_limit_reached": points_result["points_limit_reached"]}


@router.get("/checkin-items/{item_id}/records")
async def get_checkin_records(
    item_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.id == item_id,
            HealthCheckInItem.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="打卡项不存在")

    query = select(HealthCheckInRecord).where(
        HealthCheckInRecord.item_id == item_id,
        HealthCheckInRecord.user_id == current_user.id,
    )
    count_query = select(func.count(HealthCheckInRecord.id)).where(
        HealthCheckInRecord.item_id == item_id,
        HealthCheckInRecord.user_id == current_user.id,
    )

    if start_date:
        query = query.where(HealthCheckInRecord.check_in_date >= start_date)
        count_query = count_query.where(HealthCheckInRecord.check_in_date >= start_date)
    if end_date:
        query = query.where(HealthCheckInRecord.check_in_date <= end_date)
        count_query = count_query.where(HealthCheckInRecord.check_in_date <= end_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(HealthCheckInRecord.check_in_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [HealthCheckInRecordResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ──────────────── 模板分类 ────────────────


@router.get("/template-categories")
async def list_template_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanTemplateCategory)
        .where(PlanTemplateCategory.status == "active")
        .order_by(PlanTemplateCategory.sort_order.asc())
    )
    categories = result.scalars().all()
    items = [PlanTemplateCategoryResponse.model_validate(c) for c in categories]
    return {"items": items}


@router.get("/template-categories/{category_id}")
async def get_template_category_detail(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanTemplateCategory).where(PlanTemplateCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    rec_result = await db.execute(
        select(RecommendedPlan)
        .where(RecommendedPlan.category_id == category_id, RecommendedPlan.is_published == True)
        .options(selectinload(RecommendedPlan.tasks))
        .order_by(RecommendedPlan.sort_order.asc())
    )
    recommended_plans = [
        RecommendedPlanResponse.model_validate(p) for p in rec_result.scalars().all()
    ]

    user_result = await db.execute(
        select(UserPlan)
        .where(UserPlan.user_id == current_user.id, UserPlan.category_id == category_id, UserPlan.status == "active")
        .options(selectinload(UserPlan.tasks))
        .order_by(UserPlan.created_at.desc())
    )
    user_plans = [UserPlanResponse.model_validate(p) for p in user_result.scalars().all()]

    return {
        "category": PlanTemplateCategoryResponse.model_validate(category),
        "recommended_plans": recommended_plans,
        "user_plans": user_plans,
    }


# ──────────────── 推荐计划 ────────────────


@router.get("/recommended-plans/{plan_id}")
async def get_recommended_plan_detail(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan)
        .options(selectinload(RecommendedPlan.tasks), selectinload(RecommendedPlan.category))
        .where(RecommendedPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="推荐计划不存在")

    resp = RecommendedPlanResponse.model_validate(plan)
    resp.tasks = [RecommendedPlanTaskResponse.model_validate(t) for t in plan.tasks]
    resp.category_name = plan.category.name if plan.category else None
    return resp


@router.post("/recommended-plans/{plan_id}/join")
async def join_recommended_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan)
        .options(selectinload(RecommendedPlan.tasks))
        .where(RecommendedPlan.id == plan_id, RecommendedPlan.is_published == True)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="推荐计划不存在或已下架")

    user_plan = UserPlan(
        user_id=current_user.id,
        category_id=plan.category_id,
        source_type="recommended",
        recommended_plan_id=plan.id,
        plan_name=plan.name,
        description=plan.description,
        duration_days=plan.duration_days,
        current_day=1,
        status="active",
        start_date=date.today(),
    )
    db.add(user_plan)
    await db.flush()

    for t in plan.tasks:
        task = UserPlanTask(
            plan_id=user_plan.id,
            user_id=current_user.id,
            task_name=t.task_name,
            target_value=t.target_value,
            target_unit=t.target_unit,
            sort_order=t.sort_order,
        )
        db.add(task)

    await db.flush()
    await db.refresh(user_plan)
    return {"message": "加入成功", "plan_id": user_plan.id}


# ──────────────── 用户计划 ────────────────


@router.post("/user-plans", response_model=UserPlanResponse)
async def create_user_plan(
    data: UserPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_plan = UserPlan(
        user_id=current_user.id,
        category_id=data.category_id,
        source_type="custom",
        plan_name=data.plan_name,
        description=data.description,
        duration_days=data.duration_days,
        current_day=1,
        status="active",
        start_date=date.today(),
    )
    db.add(user_plan)
    await db.flush()

    if data.tasks:
        for t in data.tasks:
            task = UserPlanTask(
                plan_id=user_plan.id,
                user_id=current_user.id,
                task_name=t.task_name,
                target_value=t.target_value,
                target_unit=t.target_unit,
                sort_order=t.sort_order,
            )
            db.add(task)
        await db.flush()

    await db.flush()
    result = await db.execute(
        select(UserPlan)
        .where(UserPlan.id == user_plan.id)
        .options(selectinload(UserPlan.tasks))
    )
    user_plan = result.scalar_one()
    return UserPlanResponse.model_validate(user_plan)


@router.get("/user-plans")
async def list_user_plans(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UserPlan).where(UserPlan.user_id == current_user.id)
    count_query = select(func.count(UserPlan.id)).where(UserPlan.user_id == current_user.id)

    if status:
        query = query.where(UserPlan.status == status)
        count_query = count_query.where(UserPlan.status == status)
    else:
        query = query.where(UserPlan.status != "deleted")
        count_query = count_query.where(UserPlan.status != "deleted")

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(UserPlan.category), selectinload(UserPlan.tasks))
        .order_by(UserPlan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    plans = result.scalars().all()
    items = []
    for p in plans:
        resp = UserPlanResponse.model_validate(p)
        resp.category_name = p.category.name if p.category else None
        items.append(resp)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/user-plans/{plan_id}")
async def get_user_plan_detail(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPlan)
        .options(selectinload(UserPlan.tasks), selectinload(UserPlan.category))
        .where(UserPlan.id == plan_id, UserPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")

    today = date.today()
    task_ids = [t.id for t in plan.tasks]
    completed_task_ids: set = set()
    if task_ids:
        rec_result = await db.execute(
            select(UserPlanTaskRecord.task_id).where(
                UserPlanTaskRecord.task_id.in_(task_ids),
                UserPlanTaskRecord.user_id == current_user.id,
                UserPlanTaskRecord.check_in_date == today,
                UserPlanTaskRecord.is_completed == True,
            )
        )
        completed_task_ids = {row[0] for row in rec_result.all()}

    resp = UserPlanResponse.model_validate(plan)
    resp.category_name = plan.category.name if plan.category else None
    resp.tasks = []
    for t in sorted(plan.tasks, key=lambda x: x.sort_order):
        task_resp = UserPlanTaskResponse.model_validate(t)
        task_resp.today_completed = t.id in completed_task_ids
        resp.tasks.append(task_resp)

    return resp


@router.put("/user-plans/{plan_id}", response_model=UserPlanResponse)
async def update_user_plan(
    plan_id: int,
    data: UserPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPlan)
        .where(UserPlan.id == plan_id, UserPlan.user_id == current_user.id)
        .options(selectinload(UserPlan.tasks))
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.flush()
    await db.refresh(plan)
    result = await db.execute(
        select(UserPlan)
        .where(UserPlan.id == plan_id)
        .options(selectinload(UserPlan.tasks))
    )
    plan = result.scalar_one()
    return UserPlanResponse.model_validate(plan)


@router.delete("/user-plans/{plan_id}")
async def delete_user_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPlan).where(UserPlan.id == plan_id, UserPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    plan.status = "deleted"
    await db.flush()
    return {"message": "删除成功"}


@router.post("/user-plans/{plan_id}/tasks/{task_id}/checkin")
async def checkin_plan_task(
    plan_id: int,
    task_id: int,
    data: UserPlanTaskCheckInCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPlanTask).where(
            UserPlanTask.id == task_id,
            UserPlanTask.plan_id == plan_id,
            UserPlanTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    today = date.today()
    existing = await db.execute(
        select(UserPlanTaskRecord).where(
            UserPlanTaskRecord.task_id == task_id,
            UserPlanTaskRecord.user_id == current_user.id,
            UserPlanTaskRecord.check_in_date == today,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="今日已打卡")

    record = UserPlanTaskRecord(
        task_id=task_id,
        user_id=current_user.id,
        check_in_date=today,
        actual_value=data.actual_value,
        is_completed=True,
        check_in_time=datetime.utcnow(),
    )
    db.add(record)
    points_result = {"points_earned": 0, "points_limit_reached": False}
    try:
        from app.services.checkin_points_service import award_checkin_points
        points_result = await award_checkin_points(db, current_user, "健康计划任务打卡")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"打卡积分发放异常: {e}")
    await db.flush()
    return {"message": "打卡成功", "points_earned": points_result["points_earned"], "points_limit_reached": points_result["points_limit_reached"]}


# ──────────────── AI 生成计划 ────────────────


@router.post("/ai-generate")
async def ai_generate_plan(
    data: AIGeneratePlanV2Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(
        select(HealthProfile).where(HealthProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=400, detail="请先完善您的健康档案后再生成AI计划")

    required_fields = [profile.gender, profile.birthday, profile.height, profile.weight]
    if not all(required_fields):
        raise HTTPException(status_code=400, detail="健康档案信息不完整，请至少填写性别、出生日期、身高、体重")

    user_profile = {
        "gender": profile.gender,
        "birthday": str(profile.birthday) if profile.birthday else None,
        "height": profile.height,
        "weight": profile.weight,
        "smoking": profile.smoking,
        "drinking": profile.drinking,
        "exercise_habit": profile.exercise_habit,
        "sleep_habit": profile.sleep_habit,
        "chronic_diseases": profile.chronic_diseases,
    }

    # deactivate old AI-generated plans (without category)
    old_plans_result = await db.execute(
        select(UserPlan).where(
            UserPlan.user_id == current_user.id,
            UserPlan.source_type == "ai",
            UserPlan.category_id.is_(None),
            UserPlan.status == "active",
        )
    )
    for old_plan in old_plans_result.scalars().all():
        old_plan.status = "replaced"

    system_prompt = (
        "你是一位专业的AI健康规划师。请根据用户的健康档案信息，生成个性化的健康计划。"
        "回复请用JSON格式: {\"plan_name\": \"...\", \"description\": \"...\", "
        "\"duration_days\": 30, \"tasks\": [{\"task_name\": \"...\", \"target_value\": 8000, "
        "\"target_unit\": \"步\", \"sort_order\": 0}]}"
    )
    profile_str = json.dumps(user_profile, ensure_ascii=False, default=str)
    content = f"我的健康档案: {profile_str}"
    if data.goals:
        content += f"\n我的目标: {data.goals}"
    messages = [{"role": "user", "content": content}]
    result_text = await call_ai_model(messages, system_prompt, db)

    try:
        cleaned = result_text.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n")
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        ai_plan = json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        ai_plan = {
            "plan_name": "AI个性化健康计划",
            "description": result_text[:500] if result_text else "AI生成的健康计划",
            "duration_days": 30,
            "tasks": [],
        }

    user_plan = UserPlan(
        user_id=current_user.id,
        source_type="ai",
        plan_name=ai_plan.get("plan_name", "AI健康计划"),
        description=ai_plan.get("description"),
        duration_days=ai_plan.get("duration_days", 30),
        current_day=1,
        status="active",
        start_date=date.today(),
    )
    db.add(user_plan)
    await db.flush()

    for i, task_data in enumerate(ai_plan.get("tasks", [])):
        task = UserPlanTask(
            plan_id=user_plan.id,
            user_id=current_user.id,
            task_name=task_data.get("task_name", "健康任务"),
            target_value=task_data.get("target_value"),
            target_unit=task_data.get("target_unit"),
            sort_order=task_data.get("sort_order", i),
        )
        db.add(task)

    await db.flush()
    await db.refresh(user_plan)
    return {"message": "AI计划生成成功", "plan_id": user_plan.id}


@router.post("/ai-generate-category/{category_id}")
async def ai_generate_category_plan(
    category_id: int,
    data: AIGenerateCategoryPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cat_result = await db.execute(
        select(PlanTemplateCategory).where(PlanTemplateCategory.id == category_id)
    )
    category = cat_result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    profile_result = await db.execute(
        select(HealthProfile).where(HealthProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=400, detail="请先完善您的健康档案后再生成AI计划")

    required_fields = [profile.gender, profile.birthday, profile.height, profile.weight]
    if not all(required_fields):
        raise HTTPException(status_code=400, detail="健康档案信息不完整，请至少填写性别、出生日期、身高、体重")

    user_profile = {
        "gender": profile.gender,
        "birthday": str(profile.birthday) if profile.birthday else None,
        "height": profile.height,
        "weight": profile.weight,
        "chronic_diseases": profile.chronic_diseases,
    }

    # deactivate old AI-generated plans for this category
    old_plans_result = await db.execute(
        select(UserPlan).where(
            UserPlan.user_id == current_user.id,
            UserPlan.source_type == "ai",
            UserPlan.category_id == category_id,
            UserPlan.status == "active",
        )
    )
    for old_plan in old_plans_result.scalars().all():
        old_plan.status = "replaced"

    system_prompt = (
        f"你是一位专业的AI健康规划师。请为用户生成一个「{category.name}」类型的个性化健康计划。"
        "回复请用JSON格式: {\"plan_name\": \"...\", \"description\": \"...\", "
        "\"duration_days\": 30, \"tasks\": [{\"task_name\": \"...\", \"target_value\": null, "
        "\"target_unit\": null, \"sort_order\": 0}]}"
    )
    profile_str = json.dumps(user_profile, ensure_ascii=False, default=str)
    content = f"计划分类: {category.name}\n我的健康档案: {profile_str}"
    if data.goals:
        content += f"\n我的目标: {data.goals}"
    messages = [{"role": "user", "content": content}]
    result_text = await call_ai_model(messages, system_prompt, db)

    try:
        cleaned = result_text.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n")
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        ai_plan = json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        ai_plan = {
            "plan_name": f"AI{category.name}计划",
            "description": result_text[:500] if result_text else "",
            "duration_days": 30,
            "tasks": [],
        }

    user_plan = UserPlan(
        user_id=current_user.id,
        category_id=category_id,
        source_type="ai",
        plan_name=ai_plan.get("plan_name", f"AI{category.name}计划"),
        description=ai_plan.get("description"),
        duration_days=ai_plan.get("duration_days", 30),
        current_day=1,
        status="active",
        start_date=date.today(),
    )
    db.add(user_plan)
    await db.flush()

    for i, task_data in enumerate(ai_plan.get("tasks", [])):
        task = UserPlanTask(
            plan_id=user_plan.id,
            user_id=current_user.id,
            task_name=task_data.get("task_name", "健康任务"),
            target_value=task_data.get("target_value"),
            target_unit=task_data.get("target_unit"),
            sort_order=task_data.get("sort_order", i),
        )
        db.add(task)

    await db.flush()
    await db.refresh(user_plan)
    return {"message": "AI计划生成成功", "plan_id": user_plan.id}


# ──────────────── 今日待办 ────────────────


@router.get("/today-todos", response_model=TodayTodoResponse)
async def get_today_todos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    groups: list[TodayTodoGroup] = []
    total_completed = 0
    total_count = 0

    # 1. medication group (always present)
    med_result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status == "active",
            MedicationReminder.is_paused == False,
        )
    )
    medications = med_result.scalars().all()
    med_checkin_result = await db.execute(
        select(MedicationCheckIn.reminder_id).where(
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == today,
        )
    )
    med_checked_ids = {row[0] for row in med_checkin_result.all()}

    med_items = []
    for m in sorted(medications, key=lambda x: (x.remind_time or "99:99")):
        is_done = m.id in med_checked_ids
        med_items.append(TodayTodoItem(
            id=m.id,
            name=m.medicine_name,
            type="medication",
            source="medication_reminder",
            source_id=m.id,
            is_completed=is_done,
            remind_time=m.remind_time,
            extra={"dosage": m.dosage, "time_period": m.time_period},
        ))

    med_completed = sum(1 for i in med_items if i.is_completed)
    groups.append(TodayTodoGroup(
        group_name="用药提醒",
        group_type="medication",
        items=med_items,
        completed_count=med_completed,
        total_count=len(med_items),
        is_empty=len(med_items) == 0,
    ))
    total_completed += med_completed
    total_count += len(med_items)

    # 2. checkin group (always present)
    checkin_result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.user_id == current_user.id,
            HealthCheckInItem.status == "active",
        )
    )
    checkin_items_db = checkin_result.scalars().all()
    checkin_record_result = await db.execute(
        select(HealthCheckInRecord.item_id).where(
            HealthCheckInRecord.user_id == current_user.id,
            HealthCheckInRecord.check_in_date == today,
            HealthCheckInRecord.is_completed == True,
        )
    )
    checkin_completed_ids = {row[0] for row in checkin_record_result.all()}

    checkin_todo_items = []
    for ci in checkin_items_db:
        first_time = ci.remind_times[0] if ci.remind_times and len(ci.remind_times) > 0 else None
        is_done = ci.id in checkin_completed_ids
        checkin_todo_items.append(TodayTodoItem(
            id=ci.id,
            name=ci.name,
            type="checkin",
            source="health_checkin",
            source_id=ci.id,
            target_value=ci.target_value,
            target_unit=ci.target_unit,
            is_completed=is_done,
            remind_time=first_time,
        ))
    checkin_todo_items.sort(key=lambda x: (x.remind_time or "99:99"))

    ci_completed = sum(1 for i in checkin_todo_items if i.is_completed)
    groups.append(TodayTodoGroup(
        group_name="健康打卡",
        group_type="checkin",
        items=checkin_todo_items,
        completed_count=ci_completed,
        total_count=len(checkin_todo_items),
        is_empty=len(checkin_todo_items) == 0,
    ))
    total_completed += ci_completed
    total_count += len(checkin_todo_items)

    # 3. custom plans — flat list (no sub_groups)
    plan_result = await db.execute(
        select(UserPlan)
        .options(selectinload(UserPlan.tasks))
        .where(UserPlan.user_id == current_user.id, UserPlan.status == "active")
    )
    user_plans = plan_result.scalars().all()

    all_task_ids = []
    for p in user_plans:
        all_task_ids.extend([t.id for t in p.tasks])

    plan_completed_ids: set = set()
    if all_task_ids:
        ptr_result = await db.execute(
            select(UserPlanTaskRecord.task_id).where(
                UserPlanTaskRecord.task_id.in_(all_task_ids),
                UserPlanTaskRecord.user_id == current_user.id,
                UserPlanTaskRecord.check_in_date == today,
                UserPlanTaskRecord.is_completed == True,
            )
        )
        plan_completed_ids = {row[0] for row in ptr_result.all()}

    plan_todo_items: list[TodayTodoItem] = []
    for p in user_plans:
        for t in sorted(p.tasks, key=lambda x: x.sort_order):
            is_done = t.id in plan_completed_ids
            plan_todo_items.append(TodayTodoItem(
                id=t.id,
                name=t.task_name,
                type="plan_task",
                source="user_plan",
                source_id=p.id,
                target_value=t.target_value,
                target_unit=t.target_unit,
                is_completed=is_done,
                extra={"plan_name": p.plan_name},
            ))

    plan_completed = sum(1 for i in plan_todo_items if i.is_completed)
    groups.append(TodayTodoGroup(
        group_name="健康计划",
        group_type="custom",
        items=plan_todo_items,
        completed_count=plan_completed,
        total_count=len(plan_todo_items),
        is_empty=len(plan_todo_items) == 0,
    ))
    total_completed += plan_completed
    total_count += len(plan_todo_items)

    return TodayTodoResponse(
        groups=groups,
        total_completed=total_completed,
        total_count=total_count,
    )


# ──────────────── 快速打卡 ────────────────


@router.post("/today-todos/{item_id}/check")
async def quick_check_in(
    item_id: int,
    data: QuickCheckInRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    if data.type == "medication":
        result = await db.execute(
            select(MedicationReminder).where(
                MedicationReminder.id == item_id,
                MedicationReminder.user_id == current_user.id,
                MedicationReminder.status == "active",
            )
        )
        reminder = result.scalar_one_or_none()
        if not reminder:
            raise HTTPException(status_code=404, detail="用药提醒不存在")

        existing = await db.execute(
            select(MedicationCheckIn).where(
                MedicationCheckIn.reminder_id == item_id,
                MedicationCheckIn.user_id == current_user.id,
                MedicationCheckIn.check_in_date == today,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="今日已打卡")

        checkin = MedicationCheckIn(
            reminder_id=item_id,
            user_id=current_user.id,
            check_in_date=today,
            check_in_time=datetime.utcnow(),
        )
        db.add(checkin)
        points_result = {"points_earned": 0, "points_limit_reached": False}
        try:
            from app.services.checkin_points_service import award_checkin_points
            points_result = await award_checkin_points(db, current_user, "用药提醒打卡")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"打卡积分发放异常: {e}")
        await db.flush()
        return {"message": "打卡成功", "type": "medication", "points_earned": points_result["points_earned"], "points_limit_reached": points_result["points_limit_reached"]}

    elif data.type == "checkin":
        result = await db.execute(
            select(HealthCheckInItem).where(
                HealthCheckInItem.id == item_id,
                HealthCheckInItem.user_id == current_user.id,
                HealthCheckInItem.status == "active",
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="打卡项不存在")

        existing = await db.execute(
            select(HealthCheckInRecord).where(
                HealthCheckInRecord.item_id == item_id,
                HealthCheckInRecord.user_id == current_user.id,
                HealthCheckInRecord.check_in_date == today,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="今日已打卡")

        record = HealthCheckInRecord(
            item_id=item_id,
            user_id=current_user.id,
            check_in_date=today,
            actual_value=data.value,
            is_completed=True,
            check_in_time=datetime.utcnow(),
        )
        db.add(record)
        points_result = {"points_earned": 0, "points_limit_reached": False}
        try:
            from app.services.checkin_points_service import award_checkin_points
            points_result = await award_checkin_points(db, current_user, "健康习惯打卡")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"打卡积分发放异常: {e}")
        await db.flush()
        return {"message": "打卡成功", "type": "checkin", "points_earned": points_result["points_earned"], "points_limit_reached": points_result["points_limit_reached"]}

    elif data.type == "plan_task":
        result = await db.execute(
            select(UserPlanTask).where(
                UserPlanTask.id == item_id,
                UserPlanTask.user_id == current_user.id,
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="计划任务不存在")

        existing = await db.execute(
            select(UserPlanTaskRecord).where(
                UserPlanTaskRecord.task_id == item_id,
                UserPlanTaskRecord.user_id == current_user.id,
                UserPlanTaskRecord.check_in_date == today,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="今日已打卡")

        record = UserPlanTaskRecord(
            task_id=item_id,
            user_id=current_user.id,
            check_in_date=today,
            actual_value=data.value,
            is_completed=True,
            check_in_time=datetime.utcnow(),
        )
        db.add(record)
        points_result = {"points_earned": 0, "points_limit_reached": False}
        try:
            from app.services.checkin_points_service import award_checkin_points
            points_result = await award_checkin_points(db, current_user, "健康计划任务打卡")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"打卡积分发放异常: {e}")
        await db.flush()
        return {"message": "打卡成功", "type": "plan_task", "points_earned": points_result["points_earned"], "points_limit_reached": points_result["points_limit_reached"]}

    else:
        raise HTTPException(status_code=400, detail="不支持的打卡类型，请使用 medication/checkin/plan_task")


# ──────────────── 打卡统计 ────────────────


@router.get("/statistics", response_model=CheckInStatisticsResponse)
async def get_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    # today counts - medications
    med_total_result = await db.execute(
        select(func.count(MedicationReminder.id)).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status == "active",
            MedicationReminder.is_paused == False,
        )
    )
    med_total = med_total_result.scalar() or 0

    med_done_result = await db.execute(
        select(func.count(MedicationCheckIn.id)).where(
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == today,
        )
    )
    med_done = med_done_result.scalar() or 0

    # today counts - checkin items
    ci_total_result = await db.execute(
        select(func.count(HealthCheckInItem.id)).where(
            HealthCheckInItem.user_id == current_user.id,
            HealthCheckInItem.status == "active",
        )
    )
    ci_total = ci_total_result.scalar() or 0

    ci_done_result = await db.execute(
        select(func.count(HealthCheckInRecord.id)).where(
            HealthCheckInRecord.user_id == current_user.id,
            HealthCheckInRecord.check_in_date == today,
            HealthCheckInRecord.is_completed == True,
        )
    )
    ci_done = ci_done_result.scalar() or 0

    # today counts - plan tasks
    plan_result = await db.execute(
        select(UserPlan).options(selectinload(UserPlan.tasks)).where(
            UserPlan.user_id == current_user.id, UserPlan.status == "active"
        )
    )
    user_plans = plan_result.scalars().all()
    plan_task_total = sum(len(p.tasks) for p in user_plans)

    plan_done_result = await db.execute(
        select(func.count(UserPlanTaskRecord.id)).where(
            UserPlanTaskRecord.user_id == current_user.id,
            UserPlanTaskRecord.check_in_date == today,
            UserPlanTaskRecord.is_completed == True,
        )
    )
    plan_done = plan_done_result.scalar() or 0

    today_total = med_total + ci_total + plan_task_total
    today_completed = med_done + ci_done + plan_done
    today_progress = round(today_completed / today_total * 100, 1) if today_total > 0 else 0.0

    # streak_days (consecutive days with at least one check-in)
    streak = 0
    check_date = today
    while streak <= 365:
        has_any = False
        mc = await db.execute(
            select(func.count(MedicationCheckIn.id)).where(
                MedicationCheckIn.user_id == current_user.id,
                MedicationCheckIn.check_in_date == check_date,
            )
        )
        if (mc.scalar() or 0) > 0:
            has_any = True
        if not has_any:
            cr = await db.execute(
                select(func.count(HealthCheckInRecord.id)).where(
                    HealthCheckInRecord.user_id == current_user.id,
                    HealthCheckInRecord.check_in_date == check_date,
                    HealthCheckInRecord.is_completed == True,
                )
            )
            if (cr.scalar() or 0) > 0:
                has_any = True
        if not has_any:
            pr = await db.execute(
                select(func.count(UserPlanTaskRecord.id)).where(
                    UserPlanTaskRecord.user_id == current_user.id,
                    UserPlanTaskRecord.check_in_date == check_date,
                    UserPlanTaskRecord.is_completed == True,
                )
            )
            if (pr.scalar() or 0) > 0:
                has_any = True
        if has_any:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    async def _day_completion(d: date) -> tuple[int, int]:
        """Returns (completed, total) for a given date."""
        d_med = await db.execute(
            select(func.count(MedicationCheckIn.id)).where(
                MedicationCheckIn.user_id == current_user.id,
                MedicationCheckIn.check_in_date == d,
            )
        )
        d_ci = await db.execute(
            select(func.count(HealthCheckInRecord.id)).where(
                HealthCheckInRecord.user_id == current_user.id,
                HealthCheckInRecord.check_in_date == d,
                HealthCheckInRecord.is_completed == True,
            )
        )
        d_plan = await db.execute(
            select(func.count(UserPlanTaskRecord.id)).where(
                UserPlanTaskRecord.user_id == current_user.id,
                UserPlanTaskRecord.check_in_date == d,
                UserPlanTaskRecord.is_completed == True,
            )
        )
        completed = (d_med.scalar() or 0) + (d_ci.scalar() or 0) + (d_plan.scalar() or 0)
        return completed, today_total

    # weekly data + weekly_rates (last 7 days)
    weekly_data = []
    weekly_rates: list[float] = []
    for i in range(7):
        d = today - timedelta(days=6 - i)
        completed_d, total_d = await _day_completion(d)
        weekly_data.append({"date": d.isoformat(), "count": completed_d})
        weekly_rates.append(round(completed_d / total_d * 100, 1) if total_d > 0 else 0.0)

    # monthly_rates (last 30 days)
    monthly_rates: list[float] = []
    monthly_data = []
    for i in range(30):
        d = today - timedelta(days=29 - i)
        completed_d, total_d = await _day_completion(d)
        monthly_data.append({"date": d.isoformat(), "count": completed_d})
        monthly_rates.append(round(completed_d / total_d * 100, 1) if total_d > 0 else 0.0)

    # ──────────── plan_rankings (v6 修复：覆盖三类计划) ────────────
    # 修复要点：
    # 1) 关联用户 ID（原已正确）
    # 2) 覆盖自定义计划（UserPlan）+ 用药提醒（MedicationReminder）+ 健康打卡（HealthCheckInItem）
    # 3) 修正分母：以"该项目从创建日到今日的总天数 × 项目数"为分母，避免新建即 0%
    plan_rankings: list[PlanRanking] = []

    # —— 自定义计划 ——
    for p in user_plans:
        if not p.tasks:
            continue
        task_ids = [t.id for t in p.tasks]
        # 修正分母：以计划开始日到今日（含）的天数，每日所有任务都视为应完成 1 次
        if p.start_date:
            days_active = max((today - p.start_date).days + 1, 1)
        else:
            days_active = 1
        total_possible = len(task_ids) * days_active
        done_result = await db.execute(
            select(func.count(UserPlanTaskRecord.id)).where(
                UserPlanTaskRecord.task_id.in_(task_ids),
                UserPlanTaskRecord.user_id == current_user.id,
                UserPlanTaskRecord.is_completed == True,
            )
        )
        done_count = done_result.scalar() or 0
        rate = round(done_count / total_possible * 100, 1) if total_possible > 0 else 0.0
        plan_rankings.append(PlanRanking(
            plan_id=p.id,
            plan_name=p.plan_name,
            completion_rate=min(rate, 100.0),
            completed_count=done_count,
            total_count=total_possible,
        ))

    # —— 用药提醒（聚合为「用药提醒」一行） ——
    med_rem_result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status == "active",
        )
    )
    med_reminders = med_rem_result.scalars().all()
    if med_reminders:
        total_possible_med = 0
        for r in med_reminders:
            start_d = getattr(r, "start_date", None) or getattr(r, "created_at", None)
            if hasattr(start_d, "date"):
                start_d = start_d.date()
            if not start_d:
                start_d = today
            days = max((today - start_d).days + 1, 1)
            total_possible_med += days
        done_med_result = await db.execute(
            select(func.count(MedicationCheckIn.id)).where(
                MedicationCheckIn.user_id == current_user.id,
            )
        )
        done_med = done_med_result.scalar() or 0
        rate_med = (
            round(done_med / total_possible_med * 100, 1)
            if total_possible_med > 0
            else 0.0
        )
        plan_rankings.append(PlanRanking(
            plan_id=-1,
            plan_name="用药提醒",
            completion_rate=min(rate_med, 100.0),
            completed_count=done_med,
            total_count=total_possible_med,
        ))

    # —— 健康打卡（聚合为「健康打卡」一行） ——
    ci_items_result = await db.execute(
        select(HealthCheckInItem).where(
            HealthCheckInItem.user_id == current_user.id,
            HealthCheckInItem.status == "active",
        )
    )
    ci_items = ci_items_result.scalars().all()
    if ci_items:
        total_possible_ci = 0
        for it in ci_items:
            start_d = getattr(it, "created_at", None)
            if hasattr(start_d, "date"):
                start_d = start_d.date()
            if not start_d:
                start_d = today
            days = max((today - start_d).days + 1, 1)
            total_possible_ci += days
        done_ci_result = await db.execute(
            select(func.count(HealthCheckInRecord.id)).where(
                HealthCheckInRecord.user_id == current_user.id,
                HealthCheckInRecord.is_completed == True,
            )
        )
        done_ci = done_ci_result.scalar() or 0
        rate_ci = (
            round(done_ci / total_possible_ci * 100, 1)
            if total_possible_ci > 0
            else 0.0
        )
        plan_rankings.append(PlanRanking(
            plan_id=-2,
            plan_name="健康打卡",
            completion_rate=min(rate_ci, 100.0),
            completed_count=done_ci,
            total_count=total_possible_ci,
        ))

    plan_rankings.sort(key=lambda x: x.completion_rate, reverse=True)

    return CheckInStatisticsResponse(
        today_completed=today_completed,
        today_total=today_total,
        today_progress=today_progress,
        streak_days=streak,
        consecutive_days=streak,
        weekly_data=weekly_data,
        monthly_data=monthly_data,
        weekly_rates=weekly_rates,
        monthly_rates=monthly_rates,
        plan_rankings=plan_rankings,
    )
