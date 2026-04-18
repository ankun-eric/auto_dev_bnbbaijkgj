from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Coupon, CouponStatus, User, UserCoupon, UserCouponStatus
from app.schemas.coupons import CouponClaimRequest, CouponResponse, UserCouponResponse

router = APIRouter(prefix="/api/coupons", tags=["优惠券"])


@router.get("/available")
async def list_available_coupons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    query = (
        select(Coupon)
        .where(
            Coupon.status == CouponStatus.active,
            Coupon.valid_end >= now,
        )
    )
    count_query = (
        select(func.count(Coupon.id))
        .where(
            Coupon.status == CouponStatus.active,
            Coupon.valid_end >= now,
        )
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Coupon.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [CouponResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/claim")
async def claim_coupon(
    data: CouponClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coupon_result = await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))
    coupon = coupon_result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    status_val = coupon.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "active":
        raise HTTPException(status_code=400, detail="优惠券已下架")

    now = datetime.utcnow()
    if coupon.valid_end and coupon.valid_end < now:
        raise HTTPException(status_code=400, detail="优惠券已过期")

    if coupon.total_count > 0 and coupon.claimed_count >= coupon.total_count:
        raise HTTPException(status_code=400, detail="优惠券已领完")

    existing = await db.execute(
        select(UserCoupon).where(
            UserCoupon.user_id == current_user.id,
            UserCoupon.coupon_id == data.coupon_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已领取过该优惠券")

    uc = UserCoupon(
        user_id=current_user.id,
        coupon_id=data.coupon_id,
    )
    db.add(uc)
    coupon.claimed_count += 1

    await db.flush()
    return {"message": "领取成功"}


@router.get("/mine")
async def list_my_coupons(
    tab: Optional[str] = "unused",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exclude_expired: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UserCoupon).where(UserCoupon.user_id == current_user.id)
    count_query = select(func.count(UserCoupon.id)).where(UserCoupon.user_id == current_user.id)

    if tab and tab != "all":
        query = query.where(UserCoupon.status == tab)
        count_query = count_query.where(UserCoupon.status == tab)

    if exclude_expired:
        now = datetime.utcnow()
        query = query.join(Coupon, Coupon.id == UserCoupon.coupon_id).where(Coupon.valid_end >= now)
        count_query = (
            count_query.select_from(UserCoupon)
            .join(Coupon, Coupon.id == UserCoupon.coupon_id)
            .where(Coupon.valid_end >= now)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(UserCoupon.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    user_coupons = result.scalars().all()

    items = []
    for uc in user_coupons:
        coupon_result = await db.execute(select(Coupon).where(Coupon.id == uc.coupon_id))
        coupon = coupon_result.scalar_one_or_none()

        uc_data = UserCouponResponse.model_validate(uc)
        if coupon:
            uc_data.coupon = CouponResponse.model_validate(coupon)
        items.append(uc_data)

    return {"items": items, "total": total, "page": page, "page_size": page_size}
