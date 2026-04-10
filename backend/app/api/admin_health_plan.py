from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    DefaultHealthTask,
    HealthCheckInItem,
    HealthCheckInRecord,
    MedicationCheckIn,
    MedicationReminder,
    PlanTemplateCategory,
    RecommendedPlan,
    RecommendedPlanTask,
    User,
    UserPlan,
    UserPlanTask,
    UserPlanTaskRecord,
)
from app.schemas.health_plan_v2 import (
    DefaultHealthTaskCreate,
    DefaultHealthTaskResponse,
    DefaultHealthTaskUpdate,
    PlanTemplateCategoryCreate,
    PlanTemplateCategoryResponse,
    PlanTemplateCategoryUpdate,
    RecommendedPlanCreate,
    RecommendedPlanResponse,
    RecommendedPlanTaskCreate,
    RecommendedPlanTaskResponse,
    RecommendedPlanTaskUpdate,
    RecommendedPlanUpdate,
)

router = APIRouter(prefix="/api/admin/health-plan", tags=["管理端-健康计划"])


# ──────────────── 推荐计划管理 ────────────────


@router.get("/recommended-plans")
async def admin_list_recommended_plans(
    category_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(RecommendedPlan)
    count_query = select(func.count(RecommendedPlan.id))

    if category_id:
        query = query.where(RecommendedPlan.category_id == category_id)
        count_query = count_query.where(RecommendedPlan.category_id == category_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(RecommendedPlan.category), selectinload(RecommendedPlan.tasks))
        .order_by(RecommendedPlan.sort_order.asc(), RecommendedPlan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    plans = result.scalars().all()
    items = []
    for p in plans:
        resp = RecommendedPlanResponse.model_validate(p)
        resp.category_name = p.category.name if p.category else None
        items.append(resp)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/recommended-plans", response_model=RecommendedPlanResponse)
async def admin_create_recommended_plan(
    data: RecommendedPlanCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cat_result = await db.execute(
        select(PlanTemplateCategory).where(PlanTemplateCategory.id == data.category_id)
    )
    if not cat_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="分类不存在")

    plan = RecommendedPlan(
        category_id=data.category_id,
        name=data.name,
        description=data.description,
        target_audience=data.target_audience,
        duration_days=data.duration_days,
        cover_image=data.cover_image,
        is_published=data.is_published,
        sort_order=data.sort_order,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    result = await db.execute(
        select(RecommendedPlan)
        .where(RecommendedPlan.id == plan.id)
        .options(selectinload(RecommendedPlan.tasks))
    )
    plan = result.scalar_one()
    return RecommendedPlanResponse.model_validate(plan)


@router.put("/recommended-plans/{plan_id}", response_model=RecommendedPlanResponse)
async def admin_update_recommended_plan(
    plan_id: int,
    data: RecommendedPlanUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan)
        .where(RecommendedPlan.id == plan_id)
        .options(selectinload(RecommendedPlan.tasks))
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="推荐计划不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.flush()
    await db.refresh(plan)
    result = await db.execute(
        select(RecommendedPlan)
        .where(RecommendedPlan.id == plan_id)
        .options(selectinload(RecommendedPlan.tasks))
    )
    plan = result.scalar_one()
    return RecommendedPlanResponse.model_validate(plan)


@router.delete("/recommended-plans/{plan_id}")
async def admin_delete_recommended_plan(
    plan_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan).where(RecommendedPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="推荐计划不存在")

    await db.delete(plan)
    await db.flush()
    return {"message": "删除成功"}


@router.put("/recommended-plans/{plan_id}/publish")
async def admin_toggle_publish(
    plan_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan).where(RecommendedPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="推荐计划不存在")

    plan.is_published = not plan.is_published
    await db.flush()
    return {"message": "操作成功", "is_published": plan.is_published}


@router.get("/recommended-plans/{plan_id}/tasks")
async def admin_list_plan_tasks(
    plan_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan).where(RecommendedPlan.id == plan_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="推荐计划不存在")

    task_result = await db.execute(
        select(RecommendedPlanTask)
        .where(RecommendedPlanTask.plan_id == plan_id)
        .order_by(RecommendedPlanTask.sort_order.asc())
    )
    tasks = [RecommendedPlanTaskResponse.model_validate(t) for t in task_result.scalars().all()]
    return {"items": tasks}


@router.post("/recommended-plans/{plan_id}/tasks", response_model=RecommendedPlanTaskResponse)
async def admin_create_plan_task(
    plan_id: int,
    data: RecommendedPlanTaskCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlan).where(RecommendedPlan.id == plan_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="推荐计划不存在")

    task = RecommendedPlanTask(
        plan_id=plan_id,
        task_name=data.task_name,
        target_value=data.target_value,
        target_unit=data.target_unit,
        sort_order=data.sort_order,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return RecommendedPlanTaskResponse.model_validate(task)


@router.put("/recommended-plans/tasks/{task_id}", response_model=RecommendedPlanTaskResponse)
async def admin_update_plan_task(
    task_id: int,
    data: RecommendedPlanTaskUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlanTask).where(RecommendedPlanTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.flush()
    await db.refresh(task)
    return RecommendedPlanTaskResponse.model_validate(task)


@router.delete("/recommended-plans/tasks/{task_id}")
async def admin_delete_plan_task(
    task_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendedPlanTask).where(RecommendedPlanTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    await db.delete(task)
    await db.flush()
    return {"message": "删除成功"}


# ──────────────── 模板分类管理 ────────────────


@router.get("/template-categories")
async def admin_list_template_categories(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanTemplateCategory).order_by(PlanTemplateCategory.sort_order.asc())
    )
    categories = result.scalars().all()
    items = [PlanTemplateCategoryResponse.model_validate(c) for c in categories]
    return {"items": items}


@router.post("/template-categories", response_model=PlanTemplateCategoryResponse)
async def admin_create_template_category(
    data: PlanTemplateCategoryCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    category = PlanTemplateCategory(
        name=data.name,
        description=data.description,
        icon=data.icon,
        sort_order=data.sort_order,
        preset_tasks=data.preset_tasks,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return PlanTemplateCategoryResponse.model_validate(category)


@router.put("/template-categories/{category_id}", response_model=PlanTemplateCategoryResponse)
async def admin_update_template_category(
    category_id: int,
    data: PlanTemplateCategoryUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanTemplateCategory).where(PlanTemplateCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.flush()
    await db.refresh(category)
    return PlanTemplateCategoryResponse.model_validate(category)


@router.delete("/template-categories/{category_id}")
async def admin_delete_template_category(
    category_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanTemplateCategory).where(PlanTemplateCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    user_count_result = await db.execute(
        select(func.count(UserPlan.id)).where(UserPlan.category_id == category_id)
    )
    user_count = user_count_result.scalar() or 0

    category.status = "deleted"
    await db.flush()

    msg = "删除成功"
    if user_count > 0:
        msg = f"分类已标记删除，但有 {user_count} 个用户计划引用此分类，已有计划不受影响"
    return {"message": msg}


# ──────────────── 默认健康任务 ────────────────


@router.get("/default-tasks")
async def admin_list_default_tasks(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DefaultHealthTask).order_by(DefaultHealthTask.sort_order.asc())
    )
    tasks = [DefaultHealthTaskResponse.model_validate(t) for t in result.scalars().all()]
    return {"items": tasks}


@router.post("/default-tasks", response_model=DefaultHealthTaskResponse)
async def admin_create_default_task(
    data: DefaultHealthTaskCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    task = DefaultHealthTask(
        name=data.name,
        description=data.description,
        target_value=data.target_value,
        target_unit=data.target_unit,
        category_type=data.category_type,
        template_category_id=data.template_category_id,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return DefaultHealthTaskResponse.model_validate(task)


@router.put("/default-tasks/{task_id}", response_model=DefaultHealthTaskResponse)
async def admin_update_default_task(
    task_id: int,
    data: DefaultHealthTaskUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DefaultHealthTask).where(DefaultHealthTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.flush()
    await db.refresh(task)
    return DefaultHealthTaskResponse.model_validate(task)


@router.delete("/default-tasks/{task_id}")
async def admin_delete_default_task(
    task_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DefaultHealthTask).where(DefaultHealthTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    await db.delete(task)
    await db.flush()
    return {"message": "删除成功"}


# ──────────────── 打卡数据统计 ────────────────


@router.get("/checkin-statistics")
async def admin_checkin_statistics(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = today - timedelta(days=days - 1)

    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    # active checkin users today
    med_users = await db.execute(
        select(func.count(func.distinct(MedicationCheckIn.user_id))).where(
            MedicationCheckIn.check_in_date == today,
        )
    )
    ci_users = await db.execute(
        select(func.count(func.distinct(HealthCheckInRecord.user_id))).where(
            HealthCheckInRecord.check_in_date == today,
            HealthCheckInRecord.is_completed == True,
        )
    )
    plan_users = await db.execute(
        select(func.count(func.distinct(UserPlanTaskRecord.user_id))).where(
            UserPlanTaskRecord.check_in_date == today,
            UserPlanTaskRecord.is_completed == True,
        )
    )
    today_active = max(med_users.scalar() or 0, ci_users.scalar() or 0, plan_users.scalar() or 0)

    # daily trend
    daily_trend = []
    for i in range(days):
        d = start + timedelta(days=i)
        mc = await db.execute(
            select(func.count(MedicationCheckIn.id)).where(MedicationCheckIn.check_in_date == d)
        )
        cr = await db.execute(
            select(func.count(HealthCheckInRecord.id)).where(
                HealthCheckInRecord.check_in_date == d,
                HealthCheckInRecord.is_completed == True,
            )
        )
        pr = await db.execute(
            select(func.count(UserPlanTaskRecord.id)).where(
                UserPlanTaskRecord.check_in_date == d,
                UserPlanTaskRecord.is_completed == True,
            )
        )
        total_day = (mc.scalar() or 0) + (cr.scalar() or 0) + (pr.scalar() or 0)
        daily_trend.append({"date": d.isoformat(), "count": total_day})

    # medication count
    total_meds = await db.execute(
        select(func.count(MedicationReminder.id)).where(MedicationReminder.status == "active")
    )
    # checkin item count
    total_ci = await db.execute(
        select(func.count(HealthCheckInItem.id)).where(HealthCheckInItem.status == "active")
    )
    # plan count
    total_plans = await db.execute(
        select(func.count(UserPlan.id)).where(UserPlan.status == "active")
    )

    return {
        "total_users": total_users,
        "today_active_users": today_active,
        "total_medication_reminders": total_meds.scalar() or 0,
        "total_checkin_items": total_ci.scalar() or 0,
        "total_user_plans": total_plans.scalar() or 0,
        "daily_trend": daily_trend,
    }


@router.get("/user-checkin-details")
async def admin_user_checkin_details(
    user_id: Optional[int] = None,
    check_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    target_date = check_date or date.today()

    # medication checkins
    med_query = select(MedicationCheckIn).where(MedicationCheckIn.check_in_date == target_date)
    if user_id:
        med_query = med_query.where(MedicationCheckIn.user_id == user_id)

    med_result = await db.execute(med_query.order_by(MedicationCheckIn.created_at.desc()))
    med_records = med_result.scalars().all()

    # health checkin records
    ci_query = select(HealthCheckInRecord).where(
        HealthCheckInRecord.check_in_date == target_date,
        HealthCheckInRecord.is_completed == True,
    )
    if user_id:
        ci_query = ci_query.where(HealthCheckInRecord.user_id == user_id)

    ci_result = await db.execute(ci_query.order_by(HealthCheckInRecord.created_at.desc()))
    ci_records = ci_result.scalars().all()

    # plan task records
    plan_query = select(UserPlanTaskRecord).where(
        UserPlanTaskRecord.check_in_date == target_date,
        UserPlanTaskRecord.is_completed == True,
    )
    if user_id:
        plan_query = plan_query.where(UserPlanTaskRecord.user_id == user_id)

    plan_result = await db.execute(plan_query.order_by(UserPlanTaskRecord.created_at.desc()))
    plan_records = plan_result.scalars().all()

    details = []
    for r in med_records:
        details.append({
            "type": "medication",
            "user_id": r.user_id,
            "record_id": r.id,
            "source_id": r.reminder_id,
            "check_in_date": r.check_in_date.isoformat(),
            "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
        })
    for r in ci_records:
        details.append({
            "type": "checkin",
            "user_id": r.user_id,
            "record_id": r.id,
            "source_id": r.item_id,
            "check_in_date": r.check_in_date.isoformat(),
            "actual_value": r.actual_value,
            "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
        })
    for r in plan_records:
        details.append({
            "type": "plan_task",
            "user_id": r.user_id,
            "record_id": r.id,
            "source_id": r.task_id,
            "check_in_date": r.check_in_date.isoformat(),
            "actual_value": r.actual_value,
            "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
        })

    total = len(details)
    start = (page - 1) * page_size
    end = start + page_size
    paged = details[start:end]

    return {"items": paged, "total": total, "page": page, "page_size": page_size, "date": target_date.isoformat()}


@router.get("/user-daily-summary")
async def admin_user_daily_summary(
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """按用户+日期范围查看打卡汇总"""
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=6))

    users_result = await db.execute(select(User.id, User.phone, User.nickname))
    all_users = [{"id": r[0], "phone": r[1], "nickname": r[2]} for r in users_result.all()]

    daily_data = []
    current = start
    while current <= end:
        med_query = select(MedicationReminder).where(MedicationReminder.status == "active")
        if user_id:
            med_query = med_query.where(MedicationReminder.user_id == user_id)
        med_result = await db.execute(med_query)
        med_reminders = med_result.scalars().all()

        med_checkin_query = select(MedicationCheckIn).where(MedicationCheckIn.check_in_date == current)
        if user_id:
            med_checkin_query = med_checkin_query.where(MedicationCheckIn.user_id == user_id)
        med_checkin_result = await db.execute(med_checkin_query)
        med_checkins = med_checkin_result.scalars().all()
        med_checked_ids = {c.reminder_id for c in med_checkins}

        ci_query = select(HealthCheckInItem).where(HealthCheckInItem.status == "active")
        if user_id:
            ci_query = ci_query.where(HealthCheckInItem.user_id == user_id)
        ci_result = await db.execute(ci_query)
        ci_items = ci_result.scalars().all()

        ci_record_query = select(HealthCheckInRecord).where(
            HealthCheckInRecord.check_in_date == current,
            HealthCheckInRecord.is_completed == True,
        )
        if user_id:
            ci_record_query = ci_record_query.where(HealthCheckInRecord.user_id == user_id)
        ci_record_result = await db.execute(ci_record_query)
        ci_records = ci_record_result.scalars().all()
        ci_completed_ids = {r.item_id for r in ci_records}

        plan_task_query = select(UserPlanTask).join(UserPlan).where(UserPlan.status == "active")
        if user_id:
            plan_task_query = plan_task_query.where(UserPlanTask.user_id == user_id)
        plan_task_result = await db.execute(plan_task_query)
        plan_tasks = plan_task_result.scalars().all()

        plan_record_query = select(UserPlanTaskRecord).where(
            UserPlanTaskRecord.check_in_date == current,
            UserPlanTaskRecord.is_completed == True,
        )
        if user_id:
            plan_record_query = plan_record_query.where(UserPlanTaskRecord.user_id == user_id)
        plan_record_result = await db.execute(plan_record_query)
        plan_records = plan_record_result.scalars().all()
        plan_completed_ids = {r.task_id for r in plan_records}

        total_expected = len(med_reminders) + len(ci_items) + len(plan_tasks)
        total_completed = len(med_checked_ids) + len(ci_completed_ids) + len(plan_completed_ids)

        details = []
        for m in med_reminders:
            details.append({
                "name": m.medicine_name,
                "type": "medication",
                "is_completed": m.id in med_checked_ids,
                "check_time": next((c.check_in_time.isoformat() for c in med_checkins if c.reminder_id == m.id), None),
            })
        for ci in ci_items:
            record = next((r for r in ci_records if r.item_id == ci.id), None)
            details.append({
                "name": ci.name,
                "type": "checkin",
                "is_completed": ci.id in ci_completed_ids,
                "check_time": record.check_in_time.isoformat() if record and record.check_in_time else None,
            })
        for pt in plan_tasks:
            record = next((r for r in plan_records if r.task_id == pt.id), None)
            details.append({
                "name": pt.task_name,
                "type": "plan_task",
                "is_completed": pt.id in plan_completed_ids,
                "check_time": record.check_in_time.isoformat() if record and record.check_in_time else None,
            })

        completion_rate = round((total_completed / total_expected * 100), 1) if total_expected > 0 else 0

        daily_data.append({
            "date": current.isoformat(),
            "total_expected": total_expected,
            "total_completed": total_completed,
            "completion_rate": completion_rate,
            "details": details,
        })

        current += timedelta(days=1)

    return {"daily_data": daily_data, "users": all_users}
