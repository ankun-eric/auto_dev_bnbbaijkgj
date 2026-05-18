"""[PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划入口改造 —— 轻量化 API 端点。

新增端点（不改造旧 health_plan_v2 接口，确保向后兼容）：

| 路径                                                | 方法 | 用途                          |
|-----------------------------------------------------|------|-------------------------------|
| /api/medication-plans/hero-count                    | GET  | Hero「在用药品」格子文案+数字 |
| /api/medication-plans/today                         | GET  | 用药提醒页 banner + 时间线   |
| /api/medication-plans/summary                       | GET  | 健康档案摘要卡（仅服药中）   |
| /api/medication-check-in                            | POST | 按 plan_id + scheduled_time 打卡 |
| /api/medication-check-in/{id}/revoke                | POST | 5 分钟内撤销打卡             |
| /api/medication-stats/monthly-compliance            | GET  | 本月依从率                   |

数据模型复用：MedicationReminder / MedicationCheckIn（不新增数据表）。

「按时间点」粒度方案（方案 A）：
- MedicationCheckIn 表只有 (reminder_id, check_in_date, check_in_time) 三个
  关键字段。本模块约定：``check_in_time`` 同时承担「实际打卡时间戳」职责，
  打卡接口入参 ``scheduled_time`` 仅用于幂等去重（同 reminder_id+date+time
  视为已打卡），不再单独落库。判定「某时间点是否已打卡」通过比较当日打卡数
  量与日计划时间点数量 + 时间窗匹配实现。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import FamilyMember, MedicationCheckIn, MedicationReminder, User
from app.services.medication_status_scheduler import auto_flow_medication_status

router = APIRouter(prefix="/api", tags=["用药计划入口 V1"])


# [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 咨询人维度过滤：按 family_member_id 过滤当前用户的提醒。
#   consultant_id 语义：None / -1 = 不过滤（兼容旧客户端，相当于本人）；0 = 本人（family_member_id IS NULL）；>0 = 指定家庭成员
def _apply_consultant_filter(stmt, consultant_id: Optional[int]):
    if consultant_id is None or consultant_id == -1:
        return stmt
    if consultant_id == 0:
        return stmt.where(MedicationReminder.family_member_id.is_(None))
    return stmt.where(MedicationReminder.family_member_id == consultant_id)

# ──────────────── 工具函数 ────────────────

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _schedule_of(r: MedicationReminder) -> list[str]:
    """每日服药时间点列表（"HH:MM"），按时间升序。"""
    out: list[str] = []
    if r.custom_times and isinstance(r.custom_times, list):
        for t in r.custom_times:
            if isinstance(t, str) and len(t) >= 4:
                out.append(t[:5] if len(t) >= 5 else t)
    elif r.remind_time:
        out.append(r.remind_time[:5])
    # 去重排序
    seen = []
    for s in out:
        if s not in seen:
            seen.append(s)
    seen.sort()
    return seen


def _is_active_today(r: MedicationReminder, today: date) -> bool:
    """是否「今日仍在服药期」（与 health_plan_v2._active_med_filter 一致）。"""
    if r.status != "active":
        return False
    if r.long_term:
        return True
    if r.start_date and r.start_date > today:
        return False
    if r.end_date is None:
        return True
    return r.end_date >= today


def _has_started(r: MedicationReminder, today: date) -> bool:
    if r.start_date is None:
        return True
    return r.start_date <= today


async def _list_today_active_reminders(
    db: AsyncSession, user_id: int, today: date,
    consultant_id: Optional[int] = None,
) -> list[MedicationReminder]:
    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    )
    stmt = _apply_consultant_filter(stmt, consultant_id)
    reminders = (await db.execute(stmt)).scalars().all()
    # start_date 校验：未开始的剔除
    return [r for r in reminders if _has_started(r, today)]


async def _today_checkins(
    db: AsyncSession, user_id: int, today: date
) -> list[MedicationCheckIn]:
    res = await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.user_id == user_id,
            MedicationCheckIn.check_in_date == today,
        )
    )
    return list(res.scalars().all())


def _format_date_str(d: date) -> str:
    return f"今日 · {d.month:02d}月{d.day:02d}日 {WEEKDAY_CN[d.weekday()]}"


# ──────────────── 1) Hero 第 4 格：在用药品 ────────────────


@router.get("/medication-plans/hero-count")
async def hero_count(
    consultant_id: Optional[int] = Query(None, description="[PRD-HEALTH-ARCHIVE-OPTIM-V1] 咨询人 family_member id；None/-1=不过滤(本人兼容)；0=本人；>0=家庭成员"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hero「今日用药」格子直接渲染数据。

    Returns:
        {
          "total_today": int,
          "done_today": int,
          "remaining_today": int,
          "status": "has_remaining"|"all_done"|"none",
          "display_text": str
        }
    """
    today = date.today()
    # 懒触发状态流转，避免完全依赖定时任务
    await auto_flow_medication_status(db, user_id=current_user.id)

    reminders = await _list_today_active_reminders(db, current_user.id, today, consultant_id=consultant_id)
    total_today = sum(len(_schedule_of(r)) for r in reminders)
    # 已打卡：在按 consultant 过滤后的 reminder 集合内统计
    reminder_ids = {r.id for r in reminders}
    if consultant_id is None or consultant_id == -1:
        checkins = await _today_checkins(db, current_user.id, today)
    else:
        all_today_checkins = await _today_checkins(db, current_user.id, today)
        checkins = [c for c in all_today_checkins if c.reminder_id in reminder_ids]
    done_today = len(checkins)
    remaining = max(total_today - done_today, 0)

    # [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18 F4-3] 文案统一为「今日用药 · N」
    if total_today == 0:
        status = "none"
        text = "今日用药 · 0"
    elif remaining == 0:
        status = "all_done"
        text = f"今日用药 · {total_today} ✓"
    else:
        status = "has_remaining"
        text = f"今日用药 · {total_today}"

    return {
        "total_today": total_today,
        "done_today": done_today,
        "remaining_today": remaining,
        "status": status,
        "display_text": text,
    }


# ──────────────── 2) 用药提醒页：今日数据 ────────────────


def _next_reminder(
    reminders: list[MedicationReminder],
    done_pairs: set[tuple[int, str]],
    now: datetime,
) -> Optional[dict]:
    """返回最近一条待打卡 reminder：{plan_id, name, scheduled_time, dosage, timing}"""
    today = now.date()
    cur_hm = now.strftime("%H:%M")
    candidates: list[tuple[str, MedicationReminder]] = []
    for r in reminders:
        for t in _schedule_of(r):
            if (r.id, t) in done_pairs:
                continue
            candidates.append((t, r))
    if not candidates:
        return None
    # 选择 >= now 的最早一条；如全部都过点了，选最早的（"待补打卡"）
    future = [c for c in candidates if c[0] >= cur_hm]
    pick = sorted(future or candidates, key=lambda x: x[0])[0]
    t, r = pick
    dosage_text = (
        f"{r.dosage_value} {r.dosage_unit}"
        if r.dosage_value and r.dosage_unit
        else (r.dosage or "")
    )
    return {
        "plan_id": r.id,
        "name": r.medicine_name,
        "scheduled_time": t,
        "time": t,
        "dosage": dosage_text,
        "timing": r.guidance or r.time_period or "",
    }


async def _monthly_compliance(
    db: AsyncSession, user_id: int, today: date
) -> dict:
    """本月依从率：rate = done / expected * 100。

    expected = 当月每条 active reminder 在「(reminder 录入日 或 start_date 取后者) ~ today」
               区间内每日 schedule 时间点之和（仅本月）。
    done     = 当月 MedicationCheckIn 数量。
    "新建过去日期 reminder 不追溯空白"：以 max(start_date, created_at.date()) 起算。
    """
    month_start = date(today.year, today.month, 1)
    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == user_id,
        MedicationReminder.status.in_(["active", "archived"]),
    )
    reminders = (await db.execute(stmt)).scalars().all()

    expected = 0
    for r in reminders:
        created_d = r.created_at.date() if r.created_at else month_start
        s = r.start_date or created_d
        # 追溯起点 = max(月初, 创建日, start_date) —— 关键：不补录空白
        begin = max(month_start, created_d, s)
        if r.end_date and not r.long_term:
            end = min(today, r.end_date)
        else:
            end = today
        if begin > end:
            continue
        schedule = _schedule_of(r)
        if not schedule:
            continue
        days = (end - begin).days + 1
        expected += days * len(schedule)

    month_end = today
    done_res = await db.execute(
        select(func.count(MedicationCheckIn.id)).where(
            MedicationCheckIn.user_id == user_id,
            MedicationCheckIn.check_in_date >= month_start,
            MedicationCheckIn.check_in_date <= month_end,
        )
    )
    done = int(done_res.scalar() or 0)
    rate = int(round(done / expected * 100)) if expected > 0 else 0
    rate = min(rate, 100)
    return {
        "month": f"{today.year}-{today.month:02d}",
        "expected": expected,
        "done": done,
        "rate_percent": rate,
    }


@router.get("/medication-plans/today")
async def reminder_today(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用药提醒页一次性返回 banner / upcoming / timeline。"""
    today = date.today()
    now = datetime.now()
    await auto_flow_medication_status(db, user_id=current_user.id)

    reminders = await _list_today_active_reminders(db, current_user.id, today)
    checkins = await _today_checkins(db, current_user.id, today)
    # 已打卡 (plan_id, scheduled_time) 集合：按打卡顺序与 schedule 顺序匹配
    done_pairs: set[tuple[int, str]] = set()
    checkin_lookup: dict[tuple[int, str], MedicationCheckIn] = {}
    by_plan: dict[int, list[MedicationCheckIn]] = {}
    for c in checkins:
        by_plan.setdefault(c.reminder_id, []).append(c)
    for r in reminders:
        schedule = _schedule_of(r)
        used = sorted(by_plan.get(r.id, []), key=lambda x: x.check_in_time or x.created_at or datetime.min)
        # 按 schedule 时间点顺序匹配打卡：第 k 个打卡 → 第 k 个 schedule 时间点
        for i, c in enumerate(used):
            if i >= len(schedule):
                break
            t = schedule[i]
            done_pairs.add((r.id, t))
            checkin_lookup[(r.id, t)] = c

    total_today = sum(len(_schedule_of(r)) for r in reminders)
    done_count = len(checkins)
    remaining_count = max(total_today - done_count, 0)

    upcoming = _next_reminder(reminders, done_pairs, now)

    # 时间线
    timeline: list[dict] = []
    cur_hm = now.strftime("%H:%M")
    # 仅取第一条"即将服用"用于 upcoming badge
    upcoming_key = (upcoming["plan_id"], upcoming["scheduled_time"]) if upcoming else None
    for r in reminders:
        schedule = _schedule_of(r)
        dosage_text = (
            f"{r.dosage_value} {r.dosage_unit}"
            if r.dosage_value and r.dosage_unit
            else (r.dosage or "")
        )
        for t in schedule:
            is_done = (r.id, t) in done_pairs
            if is_done:
                status = "done"
            elif upcoming_key == (r.id, t):
                status = "upcoming"
            elif t <= cur_hm:
                # 已过点但未打卡 —— 仍按 pending（未到时间）
                # （此处按 PRD 标准只有三个状态，过点未打卡仍标记为 pending）
                status = "pending"
            else:
                status = "pending"
            c = checkin_lookup.get((r.id, t))
            timeline.append({
                "plan_id": r.id,
                "scheduled_time": t,
                "status": status,
                "actual_time": (c.check_in_time.isoformat() if c and c.check_in_time else None),
                "name": r.medicine_name,
                "dosage": dosage_text,
                "timing": r.guidance or r.time_period or "",
                "check_in_id": c.id if c else None,
            })

    timeline.sort(key=lambda x: x["scheduled_time"])

    monthly = await _monthly_compliance(db, current_user.id, today)

    banner = {
        "date_str": _format_date_str(today),
        "total_remaining": remaining_count,
        "next_reminder": (
            {"time": upcoming["scheduled_time"], "name": upcoming["name"]} if upcoming else None
        ),
        "done_count": done_count,
        "remaining_count": remaining_count,
        "monthly_compliance": monthly["rate_percent"],
    }

    return {
        "banner": banner,
        "upcoming": upcoming,
        "timeline": timeline,
    }


# ──────────────── 3) 健康档案摘要卡：仅服药中 ────────────────


def _frequency_text(r: MedicationReminder) -> str:
    n = r.frequency_per_day or len(_schedule_of(r)) or 1
    return f"每日 {n} 次"


def _timing_text(r: MedicationReminder) -> str:
    if r.guidance:
        return r.guidance
    if r.time_period:
        return r.time_period
    return ""


@router.get("/medication-plans/summary")
async def medication_plans_summary(
    consultant_id: Optional[int] = Query(None, description="[PRD-HEALTH-ARCHIVE-OPTIM-V1] 咨询人 family_member id；None/-1=不过滤(本人兼容)；0=本人；>0=家庭成员"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """健康档案用药计划摘要卡：仅返回 status='active' 且当前在服药期的记录。

    按 created_at 倒序。
    """
    today = date.today()
    await auto_flow_medication_status(db, user_id=current_user.id)

    stmt = select(MedicationReminder).where(
        MedicationReminder.user_id == current_user.id,
        MedicationReminder.status == "active",
        or_(
            MedicationReminder.long_term == True,  # noqa: E712
            MedicationReminder.end_date.is_(None),
            MedicationReminder.end_date >= today,
        ),
    )
    stmt = _apply_consultant_filter(stmt, consultant_id)
    rows = (await db.execute(stmt)).scalars().all()
    # 仅保留已开始的
    rows = [r for r in rows if _has_started(r, today)]
    rows.sort(key=lambda r: r.created_at or datetime.min, reverse=True)

    items = []
    for r in rows:
        dosage_text = (
            f"{r.dosage_value} {r.dosage_unit}"
            if r.dosage_value and r.dosage_unit
            else (r.dosage or "")
        )
        items.append({
            "id": r.id,
            "name": r.medicine_name,
            "dosage": dosage_text,
            "frequency_text": _frequency_text(r),
            "timing_text": _timing_text(r),
            "status_text": "服用中",
            "status": "active",
        })
    return {"items": items, "total": len(items)}


# ──────────────── 4) 时间点级打卡 ────────────────


class CheckInRequest(BaseModel):
    plan_id: int = Field(..., description="MedicationReminder.id")
    scheduled_time: Optional[str] = Field(None, description="计划时间点 HH:MM；可选")


@router.post("/medication-check-in")
async def create_check_in(
    data: CheckInRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    res = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == data.plan_id,
            MedicationReminder.user_id == current_user.id,
        )
    )
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    if r.status != "active":
        raise HTTPException(status_code=400, detail="用药计划当前不可打卡")

    schedule = _schedule_of(r)
    # 幂等：同一 reminder 今日已打满 schedule 次数 → 拒绝
    existing = (await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.reminder_id == r.id,
            MedicationCheckIn.user_id == current_user.id,
            MedicationCheckIn.check_in_date == today,
        )
    )).scalars().all()
    if schedule and len(existing) >= len(schedule):
        raise HTTPException(status_code=400, detail="今日全部时间点已打卡")

    now = datetime.utcnow()
    c = MedicationCheckIn(
        reminder_id=r.id,
        user_id=current_user.id,
        check_in_date=today,
        check_in_time=now,
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return {
        "id": c.id,
        "plan_id": r.id,
        "scheduled_time": data.scheduled_time,
        "check_in_time": c.check_in_time.isoformat() if c.check_in_time else None,
        "server_time": datetime.utcnow().isoformat(),
    }


@router.post("/medication-check-in/{checkin_id}/revoke")
async def revoke_check_in(
    checkin_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """5 分钟内允许撤销。超时返回 400 + code=REVOKE_TIMEOUT。"""
    res = await db.execute(
        select(MedicationCheckIn).where(
            MedicationCheckIn.id == checkin_id,
            MedicationCheckIn.user_id == current_user.id,
        )
    )
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="打卡记录不存在")
    created = c.created_at or c.check_in_time or datetime.utcnow()
    if datetime.utcnow() - created > timedelta(minutes=5):
        raise HTTPException(
            status_code=400,
            detail={"code": "REVOKE_TIMEOUT", "message": "撤销超时（仅限 5 分钟内）"},
        )
    await db.delete(c)
    await db.flush()
    return {"message": "已撤销", "id": checkin_id}


# ──────────────── 5) 本月依从率 ────────────────


@router.get("/medication-stats/monthly-compliance")
async def monthly_compliance_api(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    return await _monthly_compliance(db, current_user.id, today)
