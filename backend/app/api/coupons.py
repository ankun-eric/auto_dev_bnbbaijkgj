"""优惠券 API（用户侧 + 兑换码核销）

V2.1 更新要点：
1. 领券中心：过滤已下架（is_offline=True）的券；返回 claimed/sold_out/button_text/button_disabled
2. 重复领取返回 409
3. 兑换码兑换：批次/码 voided_at 非空时返回 422
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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


async def _try_get_optional_user(request: Request, db: AsyncSession) -> Optional[User]:
    """V2.1：领券中心可未登录访问，未登录时返回 None。"""
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    try:
        from jose import jwt
        from app.core.config import settings as _settings
        token = auth.split(" ", 1)[1] if " " in auth else auth
        payload = jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None
        rs = await db.execute(select(User).where(User.id == int(user_id)))
        return rs.scalar_one_or_none()
    except Exception:
        return None


def _build_coupon_item(coupon: Coupon, claimed: bool, sold_out: bool) -> dict:
    """V2.1：组装领券中心 item，含 claimed/sold_out/button_text/button_disabled。"""
    base = {
        "id": coupon.id,
        "name": coupon.name,
        "type": coupon.type.value if hasattr(coupon.type, "value") else str(coupon.type),
        "condition_amount": float(coupon.condition_amount or 0),
        "discount_value": float(coupon.discount_value or 0),
        "discount_rate": float(coupon.discount_rate or 1.0),
        "scope": coupon.scope.value if hasattr(coupon.scope, "value") else str(coupon.scope),
        "scope_ids": coupon.scope_ids,
        "total_count": coupon.total_count or 0,
        "claimed_count": coupon.claimed_count or 0,
        "used_count": coupon.used_count or 0,
        "validity_days": coupon.validity_days or 30,
        "status": coupon.status.value if hasattr(coupon.status, "value") else str(coupon.status),
        "is_offline": bool(getattr(coupon, "is_offline", False)),
        "created_at": coupon.created_at.isoformat() if coupon.created_at else None,
    }
    if claimed:
        button_text = "已领取"
        button_disabled = True
    elif sold_out:
        button_text = "已抢光"
        button_disabled = True
    else:
        button_text = "领取"
        button_disabled = False
    base["claimed"] = claimed
    base["sold_out"] = sold_out
    base["button_text"] = button_text
    base["button_disabled"] = button_disabled
    return base


@router.get("/available")
async def list_available_coupons(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """领券中心：仅展示可自助领取的有效券（过滤已下架）。

    V2.1：
    - 未登录可访问，claimed 恒为 false
    - 返回 claimed / sold_out / button_text / button_disabled
    - 已下架（is_offline=True）的券不返回
    """
    current_user = await _try_get_optional_user(request, db)

    # 已下架不展示
    base_cond = [Coupon.status == CouponStatus.active, Coupon.is_offline == False]  # noqa: E712

    query = select(Coupon).where(*base_cond)
    count_query = select(func.count(Coupon.id)).where(*base_cond)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Coupon.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    coupons = result.scalars().all()

    # 批量查询当前用户已领取记录
    claimed_ids: set[int] = set()
    if current_user and coupons:
        cids = [c.id for c in coupons]
        rs = await db.execute(
            select(UserCoupon.coupon_id).where(
                UserCoupon.user_id == current_user.id,
                UserCoupon.coupon_id.in_(cids),
            )
        )
        claimed_ids = {row[0] for row in rs.all()}

    items = []
    for c in coupons:
        claimed = c.id in claimed_ids
        sold_out = bool(c.total_count and c.total_count > 0 and (c.claimed_count or 0) >= c.total_count)
        # 已领过的不算抢光（按规则：已领取优先于抢光）
        if claimed:
            sold_out = False
        items.append(_build_coupon_item(c, claimed=claimed, sold_out=sold_out))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/claim")
async def claim_coupon(
    data: CouponClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A 自助领取（领券中心，每人每券 1 张）。V2.1：重复领取返回 409。"""
    coupon_result = await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))
    coupon = coupon_result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    if getattr(coupon, "is_offline", False):
        raise HTTPException(status_code=400, detail="优惠券已下架")

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
        # V2.1：重复领取返回 409 Conflict
        raise HTTPException(status_code=409, detail="您已领取过该优惠券")

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
    """我的优惠券（按 expire_at 过滤过期）。V2.1：已下架券依然展示。"""
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
        # V2.1：单码作废校验
        if getattr(rc, "voided_at", None):
            raise HTTPException(status_code=422, detail="兑换码已作废")
        if rc.status not in ("available", "sold"):
            raise HTTPException(status_code=400, detail="兑换码已使用或已作废")
        coupon_result = await db.execute(select(Coupon).where(Coupon.id == rc.coupon_id))
        coupon = coupon_result.scalar_one_or_none()
        batch_result = await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.id == rc.batch_id))
        batch = batch_result.scalar_one_or_none()
        # V2.1：批次整批作废校验
        if batch and getattr(batch, "voided_at", None):
            raise HTTPException(status_code=422, detail="兑换码所属批次已作废")
    else:
        # 2) 一码通用
        batch_result = await db.execute(
            select(CouponCodeBatch).where(
                CouponCodeBatch.universal_code == code_str,
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="兑换码无效")
        # V2.1：批次整批作废校验（必须先于 status 校验，给出明确 422）
        if getattr(batch, "voided_at", None):
            raise HTTPException(status_code=422, detail="兑换码所属批次已作废")
        if batch.status != "active":
            raise HTTPException(status_code=422, detail="兑换码已停用")
        coupon_result = await db.execute(select(Coupon).where(Coupon.id == batch.coupon_id))
        coupon = coupon_result.scalar_one_or_none()

    if not coupon:
        raise HTTPException(status_code=404, detail="兑换码对应的优惠券不存在")

    # V2.1：已下架券允许已领的继续使用，但不允许新兑换
    if getattr(coupon, "is_offline", False):
        raise HTTPException(status_code=422, detail="该优惠券已下架，无法兑换")

    # 限领规则
    if rc:
        # 一次性唯一码：每码全局只能用 1 次
        pass
    else:
        # universal 模式：单用户 per_user_limit + 整批 claim_limit 上限
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
        # V2.1：一码通用领取上限
        cl = getattr(batch, "claim_limit", None)
        if cl:
            total_used = await db.execute(
                select(func.count(CouponGrant.id)).where(
                    CouponGrant.batch_id == batch.id,
                    CouponGrant.method == "redeem_code",
                )
            )
            if (total_used.scalar() or 0) >= cl:
                raise HTTPException(status_code=422, detail="兑换码领取人数已达上限")

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
