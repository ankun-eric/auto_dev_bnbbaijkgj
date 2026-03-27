from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Appointment, AppointmentStatus, Expert, ExpertSchedule, Notification, NotificationType, User
from app.schemas.expert import AppointmentCreate, AppointmentResponse, ExpertResponse, ExpertScheduleResponse

router = APIRouter(prefix="/api/experts", tags=["专家/医生"])


@router.get("")
async def list_experts(
    department: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Expert).where(Expert.status == "active")
    count_query = select(func.count(Expert.id)).where(Expert.status == "active")

    if department:
        query = query.where(Expert.department == department)
        count_query = count_query.where(Expert.department == department)
    if keyword:
        query = query.where(Expert.name.contains(keyword) | Expert.specialties.contains(keyword))
        count_query = count_query.where(Expert.name.contains(keyword) | Expert.specialties.contains(keyword))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Expert.rating.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ExpertResponse.model_validate(e) for e in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{expert_id}", response_model=ExpertResponse)
async def get_expert(expert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")
    return ExpertResponse.model_validate(expert)


@router.get("/{expert_id}/schedules")
async def list_schedules(
    expert_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="专家不存在")

    result = await db.execute(
        select(ExpertSchedule)
        .where(ExpertSchedule.expert_id == expert_id, ExpertSchedule.status == "active")
        .order_by(ExpertSchedule.date.asc(), ExpertSchedule.time_slot.asc())
    )
    items = [ExpertScheduleResponse.model_validate(s) for s in result.scalars().all()]
    return {"items": items}


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(
    data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Expert).where(Expert.id == data.expert_id, Expert.status == "active"))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在或不可用")

    result = await db.execute(
        select(ExpertSchedule).where(
            ExpertSchedule.id == data.schedule_id,
            ExpertSchedule.expert_id == data.expert_id,
            ExpertSchedule.status == "active",
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="该排班不存在")
    if schedule.current_appointments >= schedule.max_appointments:
        raise HTTPException(status_code=400, detail="该时段预约已满")

    existing = await db.execute(
        select(Appointment).where(
            Appointment.user_id == current_user.id,
            Appointment.schedule_id == data.schedule_id,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.confirmed]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已预约该时段")

    appointment = Appointment(
        user_id=current_user.id,
        expert_id=data.expert_id,
        schedule_id=data.schedule_id,
        appointment_date=data.appointment_date,
        time_slot=data.time_slot,
        notes=data.notes,
    )
    db.add(appointment)

    schedule.current_appointments += 1

    notification = Notification(
        user_id=current_user.id,
        title="预约成功",
        content=f"您已成功预约 {expert.name} 医生 {data.appointment_date} {data.time_slot} 的咨询。",
        type=NotificationType.system,
    )
    db.add(notification)

    await db.flush()
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)


@router.get("/appointments/my")
async def my_appointments(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Appointment).where(Appointment.user_id == current_user.id)
    count_query = select(func.count(Appointment.id)).where(Appointment.user_id == current_user.id)

    if status:
        query = query.where(Appointment.status == status)
        count_query = count_query.where(Appointment.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Appointment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [AppointmentResponse.model_validate(a) for a in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
