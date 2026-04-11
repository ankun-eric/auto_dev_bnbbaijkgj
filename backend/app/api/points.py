from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    MemberLevel,
    PointsExchange,
    PointsMallItem,
    PointsRecord,
    PointsType,
    SignInRecord,
    User,
)
from app.schemas.points import (
    MemberLevelResponse,
    PointsExchangeCreate,
    PointsExchangeResponse,
    PointsMallItemResponse,
    PointsRecordResponse,
    SignInResponse,
)

router = APIRouter(prefix="/api/points", tags=["积分与会员"])


@router.get("/balance")
async def get_balance(current_user: User = Depends(get_current_user)):
    return {"points": current_user.points, "member_level": current_user.member_level}


@router.get("/records")
async def list_records(
    points_type: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(PointsRecord).where(PointsRecord.user_id == current_user.id)
    count_query = select(func.count(PointsRecord.id)).where(PointsRecord.user_id == current_user.id)

    if points_type:
        query = query.where(PointsRecord.type == points_type)
        count_query = count_query.where(PointsRecord.type == points_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(PointsRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [PointsRecordResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/signin", response_model=SignInResponse)
async def sign_in(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    result = await db.execute(
        select(SignInRecord).where(SignInRecord.user_id == current_user.id, SignInRecord.sign_date == today)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="今日已签到")

    yesterday = today - timedelta(days=1)
    yesterday_result = await db.execute(
        select(SignInRecord).where(SignInRecord.user_id == current_user.id, SignInRecord.sign_date == yesterday)
    )
    yesterday_record = yesterday_result.scalar_one_or_none()

    consecutive_days = (yesterday_record.consecutive_days + 1) if yesterday_record else 1

    base_points = 5
    bonus = min(consecutive_days - 1, 6) * 2
    points_earned = base_points + bonus

    record = SignInRecord(
        user_id=current_user.id,
        sign_date=today,
        consecutive_days=consecutive_days,
        points_earned=points_earned,
    )
    db.add(record)

    current_user.points += points_earned

    pr = PointsRecord(
        user_id=current_user.id,
        points=points_earned,
        type=PointsType.signin,
        description=f"每日签到(连续{consecutive_days}天)",
    )
    db.add(pr)

    await db.flush()
    await db.refresh(record)
    return SignInResponse.model_validate(record)


@router.get("/mall")
async def list_mall_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(PointsMallItem.id)).where(PointsMallItem.status == "active"))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(PointsMallItem)
        .where(PointsMallItem.status == "active")
        .order_by(PointsMallItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [PointsMallItemResponse.model_validate(i) for i in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/exchange", response_model=PointsExchangeResponse)
async def exchange_item(
    data: PointsExchangeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PointsMallItem).where(PointsMallItem.id == data.item_id, PointsMallItem.status == "active"))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    if item.stock < data.quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    total_points = item.price_points * data.quantity
    if current_user.points < total_points:
        raise HTTPException(status_code=400, detail="积分不足")

    exchange = PointsExchange(
        user_id=current_user.id,
        item_id=data.item_id,
        points_spent=total_points,
        quantity=data.quantity,
        shipping_info=data.shipping_info,
    )
    db.add(exchange)

    current_user.points -= total_points
    item.stock -= data.quantity

    pr = PointsRecord(
        user_id=current_user.id,
        points=-total_points,
        type=PointsType.redeem,
        description=f"积分兑换: {item.name}",
    )
    db.add(pr)

    await db.flush()
    await db.refresh(exchange)
    return PointsExchangeResponse.model_validate(exchange)


@router.get("/checkin/today-progress")
async def get_checkin_today_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.checkin_points_service import get_today_progress
    progress = await get_today_progress(db, current_user.id)
    return progress


@router.get("/level")
async def get_member_levels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MemberLevel).order_by(MemberLevel.min_points.asc()))
    items = [MemberLevelResponse.model_validate(l) for l in result.scalars().all()]
    return {"items": items}
