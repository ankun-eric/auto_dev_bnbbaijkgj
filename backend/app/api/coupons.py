"""优惠券 API（用户侧 + 兑换码核销）

设计要点（v2 重构）：
1. 优惠券有效期仅支持「领取后 N 天」一种模式：valid_start/valid_end 已废弃，
   改用 Coupon.validity_days 控制；UserCoupon.expire_at 在领取时根据
   `granted_at + validity_days` 计算并落库。
2. 限领规则：自助/定向/新人 → 每人每券 1 张；兑换码 → 每个码每人 1 次。
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Coupon,
    CouponCodeBatch,
    CouponGrant,
    CouponRedeemCode,
    CouponStatus,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.schemas.coupons import (
    CouponClaimRequest,
    CouponResponse,
    RedeemCodeRedeemRequest,
    UserCouponResponse,
)

router = APIRouter(prefix="/api/coupons", tags=["优惠券"])


def _calc_expire_at(coupon: Coupon, base: Optional[datetime] = None) -> datetime:
    base = base or datetime.utcnow()
    days = coupon.validity_days or 30
    return base + timedelta(days=days)


@router.get("/available")
async def list_available_coupons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """领券中心：仅展示可自助领取的有效券。"""
    query = select(Coupon).where(Coupon.status == CouponStatus.active)
    count_query = select(func.count(Coupon.id)).where(Coupon.status == CouponStatus.active)

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
    """A 自助领取（领券中心，每人每券 1 张）"""
    coupon_result = await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))
    coupon = coupon_result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    status_val = coupon.status.value if hasattr(coupon.status, "value") else coupon.status
    if status_val != "active":
        raise HTTPException(status_code=400, detail="优惠券已下架")

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

    now = datetime.utcnow()
    uc = UserCoupon(
        user_id=current_user.id,
        coupon_id=data.coupon_id,
        expire_at=_calc_expire_at(coupon, now),
        source="self",
    )
    db.add(uc)
    coupon.claimed_count += 1
    await db.flush()

    grant = CouponGrant(
        coupon_id=coupon.id,
        user_id=current_user.id,
        user_phone=current_user.phone,
        method="self",
        status="granted",
        granted_at=now,
        user_coupon_id=uc.id,
    )
    db.add(grant)
    return {"message": "领取成功", "expire_at": uc.expire_at.isoformat() if uc.expire_at else None}


@router.get("/mine")
async def list_my_coupons(
    tab: Optional[str] = "unused",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exclude_expired: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """我的优惠券（按 expire_at 过滤过期）"""
    query = select(UserCoupon).where(UserCoupon.user_id == current_user.id)
    count_query = select(func.count(UserCoupon.id)).where(UserCoupon.user_id == current_user.id)

    if tab and tab != "all":
        query = query.where(UserCoupon.status == tab)
        count_query = count_query.where(UserCoupon.status == tab)

    if exclude_expired:
        now = datetime.utcnow()
        query = query.where(or_(UserCoupon.expire_at.is_(None), UserCoupon.expire_at >= now))
        count_query = count_query.where(or_(UserCoupon.expire_at.is_(None), UserCoupon.expire_at >= now))

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


# ─── F：兑换码核销（用户侧）───


@router.post("/redeem")
async def redeem_code(
    data: RedeemCodeRedeemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    code_str = (data.code or "").strip()
    if not code_str:
        raise HTTPException(status_code=400, detail="请输入兑换码")

    # 简易频率限制（防爆破）：同一用户每分钟最多 10 次
    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    recent = await db.execute(
        select(func.count(CouponGrant.id)).where(
            CouponGrant.user_id == current_user.id,
            CouponGrant.method == "redeem_code",
            CouponGrant.granted_at >= one_min_ago,
        )
    )
    if (recent.scalar() or 0) >= 10:
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")

    # 1) 优先尝试一次性唯一码（unique）
    unique_code = await db.execute(
        select(CouponRedeemCode).where(CouponRedeemCode.code == code_str)
    )
    rc = unique_code.scalar_one_or_none()

    coupon: Optional[Coupon] = None
    batch: Optional[CouponCodeBatch] = None

    if rc:
        if rc.status not in ("available", "sold"):
            raise HTTPException(status_code=400, detail="兑换码已使用或已作废")
        coupon_result = await db.execute(select(Coupon).where(Coupon.id == rc.coupon_id))
        coupon = coupon_result.scalar_one_or_none()
        batch_result = await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.id == rc.batch_id))
        batch = batch_result.scalar_one_or_none()
    else:
        # 2) 一码通用
        batch_result = await db.execute(
            select(CouponCodeBatch).where(
                CouponCodeBatch.universal_code == code_str,
                CouponCodeBatch.status == "active",
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="兑换码无效")
        coupon_result = await db.execute(select(Coupon).where(Coupon.id == batch.coupon_id))
        coupon = coupon_result.scalar_one_or_none()

    if not coupon:
        raise HTTPException(status_code=404, detail="兑换码对应的优惠券不存在")

    # 限领规则
    if rc:
        # 一次性唯一码：每码每人 1 次（即每码全局只能用 1 次）
        # 这里不阻止"该用户领过同款券"，但同一码不能重复用
        pass
    else:
        # universal 模式：单用户 per_user_limit
        existing = await db.execute(
            select(func.count(CouponGrant.id)).where(
                CouponGrant.user_id == current_user.id,
                CouponGrant.batch_id == batch.id,
                CouponGrant.method == "redeem_code",
            )
        )
        cnt = existing.scalar() or 0
        if cnt >= (batch.per_user_limit or 1):
            raise HTTPException(status_code=400, detail="您已兑换过该兑换码")

    now = datetime.utcnow()
    uc = UserCoupon(
        user_id=current_user.id,
        coupon_id=coupon.id,
        expire_at=_calc_expire_at(coupon, now),
        source="redeem_code",
    )
    db.add(uc)
    coupon.claimed_count += 1
    if batch:
        batch.used_count = (batch.used_count or 0) + 1
    if rc:
        rc.status = "used"
        rc.used_at = now
        rc.used_by_user_id = current_user.id
    await db.flush()

    grant = CouponGrant(
        coupon_id=coupon.id,
        user_id=current_user.id,
        user_phone=current_user.phone,
        method="redeem_code",
        status="granted",
        granted_at=now,
        user_coupon_id=uc.id,
        batch_id=batch.id if batch else None,
        redeem_code=code_str,
    )
    db.add(grant)
    return {
        "message": "兑换成功",
        "coupon": CouponResponse.model_validate(coupon).model_dump(),
        "expire_at": uc.expire_at.isoformat() if uc.expire_at else None,
    }
