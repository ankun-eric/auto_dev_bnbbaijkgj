from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import User, UserFeedback
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackStatusUpdate

router = APIRouter(tags=["用户反馈"])

admin_dep = require_role("admin")


@router.post("/api/feedback", response_model=FeedbackResponse)
async def create_feedback(
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feedback = UserFeedback(
        user_id=current_user.id,
        feedback_type=data.feedback_type,
        description=data.description,
        images=data.images,
        contact=data.contact,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)
    return FeedbackResponse.model_validate(feedback)


@router.get("/api/feedback")
async def list_my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filter = UserFeedback.user_id == current_user.id
    count_result = await db.execute(
        select(func.count(UserFeedback.id)).where(base_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(UserFeedback)
        .where(base_filter)
        .order_by(UserFeedback.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [FeedbackResponse.model_validate(f) for f in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/api/admin/feedback")
async def admin_list_feedback(
    status: Optional[str] = None,
    feedback_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(UserFeedback)
    count_query = select(func.count(UserFeedback.id))

    if status:
        query = query.where(UserFeedback.status == status)
        count_query = count_query.where(UserFeedback.status == status)
    if feedback_type:
        query = query.where(UserFeedback.feedback_type == feedback_type)
        count_query = count_query.where(UserFeedback.feedback_type == feedback_type)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(
        query.order_by(UserFeedback.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [FeedbackResponse.model_validate(f) for f in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/api/admin/feedback/{feedback_id}/status")
async def admin_update_feedback_status(
    feedback_id: int,
    data: FeedbackStatusUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserFeedback).where(UserFeedback.id == feedback_id)
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    if data.status not in ("pending", "processing", "resolved"):
        raise HTTPException(status_code=400, detail="无效的状态值")

    feedback.status = data.status
    await db.flush()
    await db.refresh(feedback)
    return {"message": "状态更新成功", "status": feedback.status}
