from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Coupon, Favorite, User, UserCoupon
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter(prefix="/api/users", tags=["用户"])


class MyStatsResponse(BaseModel):
    points: int
    coupon_count: int
    favorite_count: int


@router.get("/me", response_model=UserResponse)
async def get_user_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.get("/me/stats", response_model=MyStatsResponse)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """聚合接口：积分 / 未过期未使用券数 / 收藏总数（不分 content_type）"""
    now = datetime.utcnow()

    coupon_count_query = (
        select(func.count(UserCoupon.id))
        .join(Coupon, Coupon.id == UserCoupon.coupon_id)
        .where(
            UserCoupon.user_id == current_user.id,
            UserCoupon.status == "unused",
            Coupon.valid_end >= now,
        )
    )
    coupon_count_result = await db.execute(coupon_count_query)
    coupon_count = coupon_count_result.scalar() or 0

    favorite_count_query = select(func.count(Favorite.id)).where(
        Favorite.user_id == current_user.id
    )
    favorite_count_result = await db.execute(favorite_count_query)
    favorite_count = favorite_count_result.scalar() or 0

    return MyStatsResponse(
        points=int(current_user.points or 0),
        coupon_count=int(coupon_count),
        favorite_count=int(favorite_count),
    )


@router.put("/me", response_model=UserResponse)
async def update_user_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.nickname is not None:
        current_user.nickname = data.nickname
    if data.avatar is not None:
        current_user.avatar = data.avatar
    current_user.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
