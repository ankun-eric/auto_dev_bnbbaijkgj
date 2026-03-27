from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import HealthPlan, HealthProfile, HealthTask, PointsRecord, PointsType, TaskCheckIn, User
from app.schemas.plan import (
    AIGeneratePlanRequest,
    HealthPlanCreate,
    HealthPlanResponse,
    HealthTaskCreate,
    HealthTaskResponse,
    TaskCheckInCreate,
)
from app.services.ai_service import generate_health_plan

router = APIRouter(prefix="/api/plans", tags=["健康计划"])


@router.post("", response_model=HealthPlanResponse)
async def create_plan(
    data: HealthPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = HealthPlan(
        user_id=current_user.id,
        plan_name=data.plan_name,
        plan_type=data.plan_type,
        content=data.content,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return HealthPlanResponse.model_validate(plan)


@router.get("")
async def list_plans(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(HealthPlan).where(HealthPlan.user_id == current_user.id)
    count_query = select(func.count(HealthPlan.id)).where(HealthPlan.user_id == current_user.id)

    if status:
        query = query.where(HealthPlan.status == status)
        count_query = count_query.where(HealthPlan.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(HealthPlan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [HealthPlanResponse.model_validate(p) for p in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{plan_id}", response_model=HealthPlanResponse)
async def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HealthPlan).where(HealthPlan.id == plan_id, HealthPlan.user_id == current_user.id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    return HealthPlanResponse.model_validate(plan)


@router.get("/{plan_id}/tasks")
async def list_tasks(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HealthPlan).where(HealthPlan.id == plan_id, HealthPlan.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="计划不存在")

    result = await db.execute(
        select(HealthTask).where(HealthTask.plan_id == plan_id).order_by(HealthTask.created_at.asc())
    )
    items = [HealthTaskResponse.model_validate(t) for t in result.scalars().all()]
    return {"items": items}


@router.post("/{plan_id}/tasks", response_model=HealthTaskResponse)
async def create_task(
    plan_id: int,
    data: HealthTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HealthPlan).where(HealthPlan.id == plan_id, HealthPlan.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="计划不存在")

    task = HealthTask(
        plan_id=plan_id,
        user_id=current_user.id,
        task_name=data.task_name,
        task_type=data.task_type,
        task_time=data.task_time,
        reminder_time=data.reminder_time,
        points_reward=data.points_reward,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return HealthTaskResponse.model_validate(task)


@router.post("/{plan_id}/tasks/{task_id}/checkin")
async def check_in_task(
    plan_id: int,
    task_id: int,
    data: TaskCheckInCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthTask).where(HealthTask.id == task_id, HealthTask.plan_id == plan_id, HealthTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    today = date.today()
    existing = await db.execute(
        select(TaskCheckIn).where(TaskCheckIn.task_id == task_id, TaskCheckIn.user_id == current_user.id, TaskCheckIn.check_in_date == today)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="今日已打卡")

    checkin = TaskCheckIn(
        task_id=task_id,
        user_id=current_user.id,
        check_in_date=today,
        notes=data.notes,
    )
    db.add(checkin)

    if task.points_reward > 0:
        current_user.points += task.points_reward
        pr = PointsRecord(
            user_id=current_user.id,
            points=task.points_reward,
            type=PointsType.task,
            description=f"任务打卡: {task.task_name}",
        )
        db.add(pr)

    await db.flush()
    return {"message": "打卡成功", "points_earned": task.points_reward}


@router.post("/ai-generate", response_model=HealthPlanResponse)
async def ai_generate_plan(
    data: AIGeneratePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()

    user_profile = {}
    if profile:
        user_profile = {
            "gender": profile.gender,
            "birthday": str(profile.birthday) if profile.birthday else None,
            "height": profile.height,
            "weight": profile.weight,
            "smoking": profile.smoking,
            "drinking": profile.drinking,
            "exercise_habit": profile.exercise_habit,
            "sleep_habit": profile.sleep_habit,
            "diet_habit": profile.diet_habit,
        }

    ai_plan = await generate_health_plan(user_profile, data.plan_type, data.goals, db)

    plan = HealthPlan(
        user_id=current_user.id,
        plan_name=ai_plan.get("plan_name", "AI健康计划"),
        plan_type=ai_plan.get("plan_type", data.plan_type or "comprehensive"),
        content=ai_plan.get("content"),
        ai_generated=True,
        start_date=date.today(),
    )
    db.add(plan)
    await db.flush()

    for task_data in ai_plan.get("tasks", []):
        task = HealthTask(
            plan_id=plan.id,
            user_id=current_user.id,
            task_name=task_data.get("task_name", "健康任务"),
            task_type=task_data.get("task_type"),
            task_time=task_data.get("task_time"),
            points_reward=task_data.get("points_reward", 10),
        )
        db.add(task)

    await db.flush()
    await db.refresh(plan)
    return HealthPlanResponse.model_validate(plan)
