"""[PRD-HEALTH-DASHBOARD-V1] 家人健康看板 API。

8 个端点：
- GET    /api/health-dashboard/{member_id}              看板汇总
- GET    /api/health-dashboard/{member_id}/trends        趋势曲线
- POST   /api/health-reminders                           创建提醒
- GET    /api/health-reminders                           提醒列表
- PUT    /api/health-reminders/{id}                      更新提醒
- DELETE /api/health-reminders/{id}                      删除提醒
- GET    /api/health-reminders/recommendations           体检推荐
- POST   /api/health-alerts/check                        异常检查
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    CheckupReport,
    FamilyManagement,
    FamilyMember,
    HealthReminder,
    User,
)
from app.schemas.health_dashboard import (
    CheckupRecommendation,
    CheckupSummary,
    HealthAlertCheckRequest,
    HealthAlertCheckResponse,
    HealthDashboardResponse,
    HealthReminderCreate,
    HealthReminderListResponse,
    HealthReminderResponse,
    HealthReminderUpdate,
    HealthScoreDetails,
    HealthTrendsResponse,
    LatestVitals,
    MedicationSummary,
    NormalRanges,
    VitalItem,
)
from app.services.health_dashboard_service import (
    NORMAL_RANGES,
    calculate_health_score,
    cancel_recheck_if_data_recorded,
    check_and_alert,
    get_checkup_recommendations,
    get_checkup_summary,
    get_latest_vitals,
    get_medication_summary,
    get_today_events,
    get_trends,
    verify_member_access,
    _get_profile_for_member,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["家人健康看板"])


# ─── API 1: 看板汇总 ──────────────────────────────────────────────────

@router.get("/api/health-dashboard/{member_id}", response_model=HealthDashboardResponse)
async def get_health_dashboard(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member = await verify_member_access(db, member_id, current_user.id)
    if not member:
        raise HTTPException(status_code=403, detail="无权查看该家庭成员的健康看板")

    profile = await _get_profile_for_member(db, member)

    # Health score
    if profile:
        score, score_details = await calculate_health_score(db, profile, member)
    else:
        score, score_details = 0, {
            "blood_pressure_score": 0, "blood_sugar_score": 0,
            "heart_rate_score": 0, "medication_score": 0, "regularity_score": 0,
        }

    # Latest vitals
    vitals_raw = {}
    if profile:
        vitals_raw = await get_latest_vitals(db, profile.id)

    latest_vitals = LatestVitals(
        blood_pressure=VitalItem(**(vitals_raw.get("blood_pressure") or {})) if vitals_raw.get("blood_pressure") else None,
        blood_sugar=VitalItem(**(vitals_raw.get("blood_sugar") or {})) if vitals_raw.get("blood_sugar") else None,
        heart_rate=VitalItem(**(vitals_raw.get("heart_rate") or {})) if vitals_raw.get("heart_rate") else None,
    )

    # Today events
    today = date.today()
    today_events = []
    if profile:
        today_events = await get_today_events(db, profile.id, member, today)

    # Medication summary
    med_summary = await get_medication_summary(db, member, today)

    # Checkup summary
    ckup_summary = await get_checkup_summary(db, member)

    return HealthDashboardResponse(
        member_id=member_id,
        member_name=member.nickname or "",
        health_score=score,
        health_score_details=HealthScoreDetails(**score_details),
        latest_vitals=latest_vitals,
        today_events=today_events,
        medication_summary=MedicationSummary(**med_summary),
        checkup_summary=CheckupSummary(**ckup_summary),
    )


# ─── API 2: 趋势曲线 ─────────────────────────────────────────────────

@router.get("/api/health-dashboard/{member_id}/trends", response_model=HealthTrendsResponse)
async def get_health_trends(
    member_id: int,
    days: int = Query(7, ge=1, le=90),
    metric: Optional[str] = Query(None, pattern=r"^(blood_pressure|blood_sugar|heart_rate)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member = await verify_member_access(db, member_id, current_user.id)
    if not member:
        raise HTTPException(status_code=403, detail="无权查看该家庭成员的健康趋势")

    profile = await _get_profile_for_member(db, member)
    if not profile:
        return HealthTrendsResponse(days=days, normal_ranges=NormalRanges())

    trends = await get_trends(db, profile.id, days=days, metric=metric)

    return HealthTrendsResponse(
        days=days,
        blood_pressure=trends.get("blood_pressure", []),
        blood_sugar=trends.get("blood_sugar", []),
        heart_rate=trends.get("heart_rate", []),
        normal_ranges=NormalRanges(),
    )


# ─── API 3: 创建健康提醒 ──────────────────────────────────────────────

@router.post("/api/health-reminders", response_model=HealthReminderResponse)
async def create_health_reminder(
    body: HealthReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.member_id:
        member = await verify_member_access(db, body.member_id, current_user.id)
        if not member:
            raise HTTPException(status_code=403, detail="无权为该家庭成员创建提醒")

    reminder = HealthReminder(
        user_id=current_user.id,
        member_id=body.member_id,
        reminder_type=body.reminder_type,
        title=body.title,
        hospital=body.hospital,
        department=body.department,
        scheduled_date=body.scheduled_date,
        recurrence=body.recurrence,
        notes=body.notes,
        status="pending",
        source="manual",
        created_by=current_user.id,
    )
    db.add(reminder)
    await db.flush()
    await db.refresh(reminder)
    return HealthReminderResponse.model_validate(reminder)


# ─── API 4: 健康提醒列表 ──────────────────────────────────────────────

@router.get("/api/health-reminders", response_model=HealthReminderListResponse)
async def list_health_reminders(
    member_id: Optional[int] = Query(None),
    reminder_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Accessible member IDs: own members + guarded members
    own_member_ids_res = await db.execute(
        select(FamilyMember.id).where(FamilyMember.user_id == current_user.id)
    )
    own_member_ids = {r[0] for r in own_member_ids_res.all()}

    guarded_res = await db.execute(
        select(FamilyManagement.managed_member_id).where(
            or_(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == current_user.id,
            ),
            FamilyManagement.status == "active",
            FamilyManagement.managed_member_id.isnot(None),
        )
    )
    guarded_member_ids = {r[0] for r in guarded_res.all()}

    all_accessible = own_member_ids | guarded_member_ids

    stmt = select(HealthReminder).where(
        or_(
            HealthReminder.user_id == current_user.id,
            HealthReminder.member_id.in_(all_accessible) if all_accessible else False,
        )
    )
    count_stmt = select(func.count(HealthReminder.id)).where(
        or_(
            HealthReminder.user_id == current_user.id,
            HealthReminder.member_id.in_(all_accessible) if all_accessible else False,
        )
    )

    if member_id is not None:
        stmt = stmt.where(HealthReminder.member_id == member_id)
        count_stmt = count_stmt.where(HealthReminder.member_id == member_id)
    if reminder_type:
        stmt = stmt.where(HealthReminder.reminder_type == reminder_type)
        count_stmt = count_stmt.where(HealthReminder.reminder_type == reminder_type)
    if status:
        stmt = stmt.where(HealthReminder.status == status)
        count_stmt = count_stmt.where(HealthReminder.status == status)

    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(HealthReminder.scheduled_date.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [HealthReminderResponse.model_validate(r) for r in result.scalars().all()]

    return HealthReminderListResponse(items=items, total=total, page=page, page_size=page_size)


# ─── API 5: 更新健康提醒 ──────────────────────────────────────────────

@router.put("/api/health-reminders/{reminder_id}", response_model=HealthReminderResponse)
async def update_health_reminder(
    reminder_id: int,
    body: HealthReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(HealthReminder).where(HealthReminder.id == reminder_id))
    reminder = res.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")

    # Only owner, creator, or guardian of the member can update
    has_access = (reminder.user_id == current_user.id or reminder.created_by == current_user.id)
    if not has_access and reminder.member_id:
        member = await verify_member_access(db, reminder.member_id, current_user.id)
        has_access = member is not None
    if not has_access:
        raise HTTPException(status_code=403, detail="无权修改该提醒")

    update_data = body.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] == "completed":
        update_data["completed_at"] = datetime.utcnow()

    for k, v in update_data.items():
        setattr(reminder, k, v)

    await db.flush()
    await db.refresh(reminder)
    return HealthReminderResponse.model_validate(reminder)


# ─── API 6: 删除健康提醒 ──────────────────────────────────────────────

@router.delete("/api/health-reminders/{reminder_id}")
async def delete_health_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(HealthReminder).where(HealthReminder.id == reminder_id))
    reminder = res.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")

    has_access = (reminder.user_id == current_user.id or reminder.created_by == current_user.id)
    if not has_access and reminder.member_id:
        member = await verify_member_access(db, reminder.member_id, current_user.id)
        has_access = member is not None
    if not has_access:
        raise HTTPException(status_code=403, detail="无权删除该提醒")

    await db.delete(reminder)
    await db.flush()
    return {"message": "提醒已删除"}


# ─── API 7: 体检推荐 ─────────────────────────────────────────────────

@router.get("/api/health-reminders/recommendations", response_model=CheckupRecommendation)
async def get_recommendations(
    member_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if member_id:
        member = await verify_member_access(db, member_id, current_user.id)
        if not member:
            raise HTTPException(status_code=403, detail="无权查看该成员信息")
    else:
        res = await db.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == current_user.id,
                FamilyMember.is_self == True,  # noqa: E712
            )
        )
        member = res.scalar_one_or_none()
        if not member:
            member = FamilyMember(
                id=0, user_id=current_user.id, relationship_type="self",
                nickname=current_user.nickname, birthday=None,
            )

    # Find latest checkup date
    latest_checkup_date = None
    if member.id:
        ck_res = await db.execute(
            select(CheckupReport.report_date)
            .where(
                CheckupReport.family_member_id == member.id,
                CheckupReport.status != "deleted",
            )
            .order_by(CheckupReport.report_date.desc())
            .limit(1)
        )
        row = ck_res.first()
        if row and row[0]:
            latest_checkup_date = row[0]

    result = get_checkup_recommendations(member, latest_checkup_date)
    return CheckupRecommendation(**result)


# ─── API 8: 异常检查 ─────────────────────────────────────────────────

@router.post("/api/health-alerts/check", response_model=HealthAlertCheckResponse)
async def check_health_alerts(
    body: HealthAlertCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """手动触发异常检查（内部调用，体征录入后自动触发）"""
    result = await check_and_alert(db, body.member_id, body.metric_type)
    return HealthAlertCheckResponse(**result)
