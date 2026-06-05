from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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


# [2026-06-05] 账号注销接口——使用独立 router 挂载到 /api/user 前缀
user_router = APIRouter(prefix="/api/user", tags=["用户"])


class DeactivateRequest(BaseModel):
    """账号注销请求"""
    code: str = ""


@user_router.post("/deactivate")
async def deactivate_account(
    data: DeactivateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注销当前账号。

    处理流程：
    1. 校验验证码（简易校验：code 不为空）
    2. 查询 FamilyMember 表：user_id = 当前用户 AND is_self != true AND status != 'deleted'
    3. 如果有家庭成员，返回错误提示
    4. 如果没有家庭成员，执行注销操作：标记 is_active=False、deleted_at=当前时间、踢出所有 token
    """
    if not data.code or not data.code.strip():
        raise HTTPException(status_code=400, detail="请输入验证码")

    from app.models.models import FamilyMember
    from app.core.password_policy import revoke_all_tokens_for_user

    family_count_result = await db.execute(
        select(func.count(FamilyMember.id)).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.is_self != True,  # noqa: E712
            FamilyMember.status != "deleted",
        )
    )
    family_count = int(family_count_result.scalar() or 0)

    if family_count > 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 1,
                "message": f"您当前还有 {family_count} 位家庭成员，请先在「健康档案-家庭成员」中删除所有家庭成员后再注销账号。",
            },
        )

    current_user.is_active = False
    current_user.deleted_at = datetime.utcnow()
    current_user.updated_at = datetime.utcnow()
    await db.flush()

    revoke_all_tokens_for_user(current_user.id)

    return {"code": 0, "message": "账号已注销"}
