import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import PointsRecord, PointsType, User
from app.schemas.user import LandingPageResponse, ShareLinkResponse

router = APIRouter(tags=["推荐"])

DEFAULT_BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


@router.get("/api/users/share-link", response_model=ShareLinkResponse)
async def get_share_link(current_user: User = Depends(get_current_user)):
    base_url = os.getenv("BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return ShareLinkResponse(
        share_link=f"{base_url}/login?ref={current_user.user_no}",
        user_no=current_user.user_no or "",
    )


@router.get("/api/landing", response_model=LandingPageResponse)
async def get_landing_page():
    return LandingPageResponse(
        brand_name="宾尼小康",
        tagline="AI智能健康管家",
        features=[
            "AI智能健康问答",
            "体检报告智能解读",
            "中医体质辨识",
            "个性化健康计划",
            "家庭健康档案管理",
        ],
    )


@router.get("/api/users/invite-stats")
async def get_invite_stats(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """我的邀请战绩：累计邀请人数、累计获得积分、邀请明细列表"""
    user_no = current_user.user_no or ""
    if not user_no:
        return {
            "total_invited": 0,
            "total_points_earned": 0,
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    count_res = await db.execute(
        select(func.count(User.id)).where(User.referrer_no == user_no)
    )
    total_invited = int(count_res.scalar() or 0)

    points_sum_res = await db.execute(
        select(func.coalesce(func.sum(PointsRecord.points), 0)).where(
            PointsRecord.user_id == current_user.id,
            PointsRecord.type == PointsType.invite,
        )
    )
    total_points = int(points_sum_res.scalar() or 0)

    list_res = await db.execute(
        select(User)
        .where(User.referrer_no == user_no)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    invited_users = list_res.scalars().all()

    items = []
    for u in invited_users:
        masked_phone = ""
        if u.phone and len(u.phone) >= 11:
            masked_phone = u.phone[:3] + "****" + u.phone[-4:]
        else:
            masked_phone = u.phone or ""
        # 该被邀请用户对应的邀请积分（按 description marker 匹配）
        marker = f"invite:user_id={u.id}"
        pr_res = await db.execute(
            select(PointsRecord).where(
                PointsRecord.user_id == current_user.id,
                PointsRecord.type == PointsType.invite,
                PointsRecord.description.like(f"%{marker}%"),
            )
        )
        pr = pr_res.scalar_one_or_none()
        items.append({
            "user_id": u.id,
            "nickname": u.nickname or masked_phone or f"用户{u.id}",
            "phone": masked_phone,
            "avatar": u.avatar,
            "registered_at": u.created_at,
            "points_awarded": pr.points if pr else 0,
        })

    return {
        "total_invited": total_invited,
        "total_points_earned": total_points,
        "items": items,
        "total": total_invited,
        "page": page,
        "page_size": page_size,
    }
