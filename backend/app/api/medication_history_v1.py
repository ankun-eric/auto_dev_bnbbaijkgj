"""[PRD-MED-HISTORY-V1] 用药提醒历史打卡记录 API。

端点：
- GET  /api/medication/calendar?year=&month=   — 月视图日历状态
- GET  /api/medication/records?date=           — 单日打卡记录详情
- POST /api/medication/supplement              — 补打卡

复用 medication_plans_v1._schedule_of 进行时间点解析。
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.medication_plans_v1 import _schedule_of
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import MedicationCheckIn, MedicationReminder, User
from app.schemas.medication_history import (
    CalendarDayOut,
    CalendarResponse,
    RecordItemOut,
    RecordsResponse,
    SupplementRequest,
    SupplementResponse,
)

router = APIRouter(prefix="/api/medication", tags=["用药历史打卡记录 V1"])
logger = logging.getLogger(__name__)


def _is_active_on_date(r: MedicationReminder, d: date) -> bool:
    """判断 reminder 在指定日期是否处于服药期（状态 active + 日期在有效期内）。"""
    if r.status != "active":
        return False
    if r.long_term:
        return True
    if r.start_date and r.start_date > d:
        return False
    if r.end_date is None:
        return True
    return r.end_date >= d


def _has_started(r: MedicationReminder, d: date) -> bool:
    if r.start_date is None:
        return True
    return r.start_date <= d


async def _active_reminders_on_date(
    db: AsyncSession, user_id: int, d: date
) -> list[MedicationReminder]:
    """获取用户在指定日期所有有效的用药提醒。"""
    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [r for r in rows if _is_active_on_date(r, d) and _has_started(r, d)]


def _days_in_month(year: int, month: int) -> int:
    """返回指定年月的天数。"""
    import calendar
    return calendar.monthrange(year, month)[1]

# ──────────────── 1) 月视图日历 ────────────────

@router.get("/calendar", response_model=CalendarResponse)
async def medication_calendar(
    year: int = Query(..., ge=2020, le=2099),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回该月每天的状态：fully_done / partial / missed / no_plan。

    - 查询所有 status=active 的 MedicationReminder
    - 按日期统计 MedicationCheckIn 数量对比 schedule 时间点数
    """
    today = date.today()
    days_total = _days_in_month(year, month)

    # 预查当月所有 active reminder（仅查一次，按日期过滤时再复用）
    all_reminders = (await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.user_id == current_user.id,
            MedicationReminder.status == "active",
        )
    )).scalars().all()

    # 预查当月所有 check_ins
    month_start = date(year, month, 1)
    month_end = date(year, month, days_total)
    checkins_res = await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date >= month_start,
            MedicationCheckIn.check_in_date <= month_end,
        )
    )
    all_checkins = list(checkins_res.scalars().all())

    # 按日期分组 check_ins
    checkins_by_date: dict[str, list[MedicationCheckIn]] = {}
    for c in all_checkins:
        k = c.check_in_date.isoformat() if isinstance(c.check_in_date, date) else str(c.check_in_date)
        checkins_by_date.setdefault(k, []).append(c)

    days_out: list[CalendarDayOut] = []
    for day in range(1, days_total + 1):
        d = date(year, month, day)
        d_str = d.isoformat()

        # 当天有效的 reminders
        active = [r for r in all_reminders if _is_active_on_date(r, d) and _has_started(r, d)]
        if not active:
            days_out.append(CalendarDayOut(date=d_str, status="no_plan"))
            continue

        total_slots = sum(len(_schedule_of(r)) for r in active)
        checkins_today = checkins_by_date.get(d_str, [])
        # 只算属于当天有效 reminder 的 check-in
        active_ids = {r.id for r in active}
        done_count = sum(1 for c in checkins_today if c.reminder_id in active_ids)

        if done_count >= total_slots and total_slots > 0:
            status = "fully_done"
        elif done_count > 0:
            status = "partial"
        else:
            status = "missed" if d < today else "no_plan"

        days_out.append(CalendarDayOut(date=d_str, status=status))

    return CalendarResponse(year=year, month=month, days=days_out)

# ──────────────── 2) 单日打卡记录详情 ────────────────

@router.get("/records", response_model=RecordsResponse)
async def medication_records(
    date_param: str = Query(..., alias="date", description="查询日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回该日所有打卡记录详情，每条记录对应一个计划时间点。

    状态判定：
    - done:       正常打卡 (check_in_type='normal')
    - supplement: 补打卡 (check_in_type='supplement')
    - missed:     未打卡且日期在 [today-2, today-1] 内，可补
    - expired:    未打卡且日期距今 >2 天，不可补
    - not_yet:    未打卡且日期 >= 今天
    """
    try:
        d = date.fromisoformat(date_param)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="日期格式错误，需为 YYYY-MM-DD")

    today = date.today()
    reminders = await _active_reminders_on_date(db, current_user.id, d)

    # 获取该日所有 check-ins
    checkins = (await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == d,
        )
    )).scalars().all()

    # 按 reminder_id 分组并排序
    checkins_by_reminder: dict[int, list[MedicationCheckIn]] = {}
    for c in checkins:
        checkins_by_reminder.setdefault(c.reminder_id, []).append(c)

    records: list[RecordItemOut] = []
    for r in reminders:
        schedule = _schedule_of(r)
        cis = sorted(
            checkins_by_reminder.get(r.id, []),
            key=lambda x: x.check_in_time or x.created_at or datetime.min,
        )

        # 将打卡按顺序映射到 schedule 时间点（与 medication_plans_v1 逻辑一致）
        done_map: dict[str, MedicationCheckIn] = {}
        for i, c in enumerate(cis):
            if i < len(schedule):
                done_map[schedule[i]] = c

        dosage_text = (
            f"{r.dosage_value} {r.dosage_unit}"
            if r.dosage_value and r.dosage_unit
            else (r.dosage or "")
        )

        for t in schedule:
            c = done_map.get(t)
            days_diff = (today - d).days if d < today else -1

            if c:
                status = "supplement" if c.check_in_type == "supplement" else "done"
                records.append(RecordItemOut(
                    plan_id=r.id,
                    drug_name=r.medicine_name,
                    dosage=dosage_text,
                    scheduled_time=t,
                    status=status,
                    check_in_time=c.check_in_time.isoformat() if c.check_in_time else None,
                    check_in_type=c.check_in_type,
                    can_supplement=False,
                ))
            else:
                if d < today:
                    if 0 < days_diff <= 2:
                        status = "missed"
                        can_supp = True
                    else:
                        status = "expired"
                        can_supp = False
                else:
                    status = "not_yet"
                    can_supp = False
                records.append(RecordItemOut(
                    plan_id=r.id,
                    drug_name=r.medicine_name,
                    dosage=dosage_text,
                    scheduled_time=t,
                    status=status,
                    check_in_time=None,
                    check_in_type=None,
                    can_supplement=can_supp,
                ))

    # 按 scheduled_time 排序
    records.sort(key=lambda x: x.scheduled_time)
    return RecordsResponse(date=date_param, records=records)

# ──────────────── 3) 补打卡 ────────────────

@router.post("/supplement", response_model=SupplementResponse)
async def medication_supplement(
    data: SupplementRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """补打卡：仅限昨日或前日漏打卡的记录（days_diff ∈ [1, 2]）。

    校验规则：
    1. plan 存在且属于当前用户
    2. 补打卡日期合法：不能是今天、不能超过 2 天前
    3. 该时间点未重复打卡
    """
    today = date.today()

    # 1) 校验日期格式
    try:
        check_date = date.fromisoformat(data.check_in_date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="日期格式错误，需为 YYYY-MM-DD")

    days_diff = (today - check_date).days

    if days_diff == 0:
        raise HTTPException(status_code=400, detail="不可补打今日，请使用正常打卡接口")
    if days_diff < 0:
        raise HTTPException(status_code=400, detail="不可补打未来日期")
    if days_diff > 2:
        raise HTTPException(status_code=400, detail="已超过补打卡时限（仅限近 2 天内）")

    # 2) 校验 plan 存在
    plan = (await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == data.plan_id,
            MedicationReminder.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    if plan.status != "active":
        raise HTTPException(status_code=400, detail="用药计划当前不可打卡")
    if not _is_active_on_date(plan, check_date):
        raise HTTPException(status_code=400, detail="该日期不在用药计划有效期内")

    # 3) 校验时间点在 schedule 中
    schedule = _schedule_of(plan)
    if data.scheduled_time not in schedule:
        raise HTTPException(status_code=400, detail="该时间点不在用药计划中")

    # 4) 检查是否已打卡（该 reminder + 日期）
    existing = (await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.reminder_id == plan.id,
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == check_date,
        )
    )).scalars().all()

    # 按打卡时间排序并匹配到 schedule 时间点
    existing_sorted = sorted(
        existing,
        key=lambda x: x.check_in_time or x.created_at or datetime.min,
    )
    done_times: set[str] = set()
    for i, c in enumerate(existing_sorted):
        if i < len(schedule):
            done_times.add(schedule[i])

    if data.scheduled_time in done_times:
        raise HTTPException(status_code=400, detail="该时间点已打卡，不可重复")

    now = datetime.now()
    c = MedicationCheckIn(
        reminder_id=plan.id,
        user_id=current_user.id,
        check_in_date=check_date,
        check_in_time=now,
        check_in_type="supplement",
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)

    return SupplementResponse(
        id=c.id,
        plan_id=plan.id,
        check_in_date=check_date.isoformat(),
        scheduled_time=data.scheduled_time,
        check_in_time=c.check_in_time.isoformat() if c.check_in_time else "",
        check_in_type="supplement",
    )
