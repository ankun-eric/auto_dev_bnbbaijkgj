"""[会员中心 PRD v1.0 对齐 - 2026-05-26] 付费会员套餐 + 用户订阅 + 收银台优惠计算 API。

接口范围：
1. 后台管理（/api/admin/membership/*）：套餐 CRUD、免费额度配置、套餐启停切换
2. 用户端查询（/api/membership/*）：可购买套餐、当前会员状态、订阅、优惠计算

字段对齐说明（与 PRD v1.0 终稿一致）：
- MembershipPlan：name/description/price_month/price_year/max_managed/
  ai_outbound_call_count/emergency_ai_call_count/max_managed_by/discount_rate/
  is_active/is_recommended/sort_order
- FreeMemberQuota：max_managed/ai_outbound_call_count/emergency_ai_call_count/max_managed_by
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub
from app.models.models import PointsRecord, PointsType, Product
from app.schemas.membership import (
    DiscountCalcRequest,
    DiscountCalcResponse,
    DiscountOptionItem,
    FreeMemberQuotaResponse,
    FreeMemberQuotaUpdate,
    MembershipMeResponse,
    MembershipPlanCreate,
    MembershipPlanResponse,
    MembershipPlanUpdate,
    MembershipSubscribeRequest,
    UserMembershipResponse,
)


admin_router = APIRouter(prefix="/api/admin/membership", tags=["付费会员-后台"])
user_router = APIRouter(prefix="/api/membership", tags=["付费会员-用户"])

admin_dep = require_role("admin")


# ──────────────── helpers ────────────────


def _plan_to_dict(p: MembershipPlan) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price_month": float(p.price_month) if p.price_month is not None else None,
        "price_year": float(p.price_year) if p.price_year is not None else None,
        "max_managed": int(p.max_managed or 0),
        "ai_outbound_call_count": int(p.ai_outbound_call_count or 0),
        "emergency_ai_call_count": int(p.emergency_ai_call_count or 0),
        "max_managed_by": int(p.max_managed_by or 0),
        "discount_rate": float(p.discount_rate) if p.discount_rate is not None else None,
        "is_active": bool(p.is_active),
        "is_recommended": bool(p.is_recommended),
        "sort_order": int(p.sort_order or 0),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _quota_to_dict(q: FreeMemberQuota) -> dict:
    return {
        "id": int(q.id),
        "max_managed": int(q.max_managed or 0),
        "ai_outbound_call_count": int(q.ai_outbound_call_count or 0),
        "emergency_ai_call_count": int(q.emergency_ai_call_count or 0),
        "max_managed_by": int(q.max_managed_by or 0),
        "updated_at": q.updated_at,
    }


async def _get_active_membership(db: AsyncSession, user_id: int) -> Optional[UserMembershipSub]:
    """获取用户当前有效（active 且未过期）的订阅。"""
    now = datetime.utcnow()
    result = await db.execute(
        select(UserMembershipSub)
        .where(UserMembershipSub.user_id == user_id)
        .where(UserMembershipSub.status == "active")
        .where(UserMembershipSub.expire_at > now)
        .order_by(UserMembershipSub.expire_at.desc())
    )
    return result.scalars().first()


async def _get_user_points_balance(db: AsyncSession, user_id: int) -> int:
    records = await db.execute(
        select(PointsRecord).where(PointsRecord.user_id == user_id)
    )
    total = 0
    for r in records.scalars().all():
        if r.points_type == PointsType.income:
            total += int(r.points or 0)
        else:
            total -= int(r.points or 0)
    return max(total, 0)


def _expire_at_for(cycle: str, start: datetime) -> datetime:
    if cycle == "yearly":
        return start + timedelta(days=365)
    return start + timedelta(days=30)


# ──────────────── 后台：套餐 CRUD ────────────────


@admin_router.get("/plans", response_model=list[MembershipPlanResponse])
async def admin_list_plans(
    include_inactive: bool = Query(True),
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MembershipPlan).order_by(MembershipPlan.sort_order.asc(), MembershipPlan.id.asc())
    if not include_inactive:
        stmt = stmt.where(MembershipPlan.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return [_plan_to_dict(p) for p in result.scalars().all()]


@admin_router.post("/plans", response_model=MembershipPlanResponse)
async def admin_create_plan(
    data: MembershipPlanCreate,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    plan = MembershipPlan(
        name=data.name,
        description=data.description,
        price_month=Decimal(str(data.price_month)) if data.price_month is not None else None,
        price_year=Decimal(str(data.price_year)) if data.price_year is not None else None,
        max_managed=int(data.max_managed),
        ai_outbound_call_count=int(data.ai_outbound_call_count),
        emergency_ai_call_count=int(data.emergency_ai_call_count),
        max_managed_by=int(data.max_managed_by),
        discount_rate=float(data.discount_rate) if data.discount_rate is not None else None,
        is_active=bool(data.is_active),
        is_recommended=bool(data.is_recommended),
        sort_order=int(data.sort_order or 0),
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return _plan_to_dict(plan)


@admin_router.get("/plans/{plan_id}", response_model=MembershipPlanResponse)
async def admin_get_plan(
    plan_id: int,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(MembershipPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    return _plan_to_dict(plan)


@admin_router.put("/plans/{plan_id}", response_model=MembershipPlanResponse)
async def admin_update_plan(
    plan_id: int,
    data: MembershipPlanUpdate,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(MembershipPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if k in ("price_month", "price_year") and v is not None:
            v = Decimal(str(v))
        setattr(plan, k, v)
    await db.flush()
    await db.refresh(plan)
    return _plan_to_dict(plan)


@admin_router.delete("/plans/{plan_id}")
async def admin_delete_plan(
    plan_id: int,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """删除套餐：若已有历史订阅引用则禁止物理删除，仅停用。"""
    plan = await db.get(MembershipPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    ref = await db.execute(
        select(UserMembershipSub).where(UserMembershipSub.plan_id == plan_id).limit(1)
    )
    if ref.scalar_one_or_none() is not None:
        plan.is_active = False
        await db.flush()
        return {"ok": True, "soft_deleted": True, "reason": "已有历史订阅引用，已自动停用"}
    await db.delete(plan)
    await db.flush()
    return {"ok": True, "hard_deleted": True}


@admin_router.put("/plans/{plan_id}/toggle", response_model=MembershipPlanResponse)
async def admin_toggle_plan(
    plan_id: int,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """启用/停用切换"""
    plan = await db.get(MembershipPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    plan.is_active = not bool(plan.is_active)
    await db.flush()
    await db.refresh(plan)
    return _plan_to_dict(plan)


# ──────────────── 后台：免费额度配置 ────────────────


async def _ensure_quota(db: AsyncSession) -> FreeMemberQuota:
    quota = await db.get(FreeMemberQuota, 1)
    if not quota:
        quota = FreeMemberQuota(
            id=1, max_managed=3, ai_outbound_call_count=5,
            emergency_ai_call_count=3, max_managed_by=3,
        )
        db.add(quota)
        await db.flush()
        await db.refresh(quota)
    return quota


@admin_router.get("/free-quota", response_model=FreeMemberQuotaResponse)
async def admin_get_free_quota(
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    quota = await _ensure_quota(db)
    return _quota_to_dict(quota)


@admin_router.put("/free-quota", response_model=FreeMemberQuotaResponse)
async def admin_update_free_quota(
    data: FreeMemberQuotaUpdate,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    quota = await _ensure_quota(db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(quota, k, v)
    await db.flush()
    await db.refresh(quota)
    return _quota_to_dict(quota)


# ──────────────── 用户端：可见套餐列表 ────────────────


@user_router.get("/plans", response_model=list[MembershipPlanResponse])
async def list_active_plans(db: AsyncSession = Depends(get_db)):
    """用户端可购买套餐（is_active=True）"""
    result = await db.execute(
        select(MembershipPlan)
        .where(MembershipPlan.is_active == True)  # noqa: E712
        .order_by(MembershipPlan.sort_order.asc(), MembershipPlan.id.asc())
    )
    return [_plan_to_dict(p) for p in result.scalars().all()]


# ──────────────── 用户端：当前会员状态 ────────────────


@user_router.get("/me", response_model=MembershipMeResponse)
async def get_my_membership(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await _get_active_membership(db, current_user.id)
    if membership and membership.plan:
        plan: MembershipPlan = membership.plan
        return MembershipMeResponse(
            is_paid_member=True,
            plan_id=plan.id,
            plan_name=plan.name,
            expire_at=membership.expire_at,
            max_managed=int(plan.max_managed or 0),
            max_managed_by=int(plan.max_managed_by or 0),
            ai_outbound_call_count=int(plan.ai_outbound_call_count or 0),
            emergency_ai_call_count=int(plan.emergency_ai_call_count or 0),
            discount_rate=float(plan.discount_rate) if plan.discount_rate is not None else None,
        )
    quota = await _ensure_quota(db)
    return MembershipMeResponse(
        is_paid_member=False,
        plan_id=None,
        plan_name="免费会员",
        expire_at=None,
        max_managed=int(quota.max_managed or 3),
        max_managed_by=int(quota.max_managed_by or 3),
        ai_outbound_call_count=int(quota.ai_outbound_call_count or 5),
        emergency_ai_call_count=int(quota.emergency_ai_call_count or 3),
        discount_rate=None,
    )


# ──────────────── 用户端：订阅 ────────────────


@user_router.post("/subscribe", response_model=UserMembershipResponse)
async def subscribe_plan(
    data: MembershipSubscribeRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(MembershipPlan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="套餐不存在或已下线")
    if data.billing_cycle not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="billing_cycle 仅允许 monthly/yearly")

    if data.billing_cycle == "monthly":
        price = plan.price_month or plan.price_year or 0
    else:
        price = plan.price_year or plan.price_month or 0

    now = datetime.utcnow()
    existing = await _get_active_membership(db, current_user.id)
    start_at = existing.expire_at if existing else now
    if existing:
        existing.status = "expired"
    expire_at = _expire_at_for(data.billing_cycle, start_at)

    record = UserMembershipSub(
        user_id=current_user.id,
        plan_id=plan.id,
        billing_cycle=data.billing_cycle,
        start_at=start_at,
        expire_at=expire_at,
        status="active",
        paid_amount=Decimal(str(price)),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return UserMembershipResponse(
        id=record.id,
        user_id=record.user_id,
        plan_id=record.plan_id,
        plan_name=plan.name,
        billing_cycle=record.billing_cycle,
        start_at=record.start_at,
        expire_at=record.expire_at,
        status=record.status,
        discount_rate=float(plan.discount_rate) if plan.discount_rate is not None else None,
        max_managed=int(plan.max_managed or 0),
        max_managed_by=int(plan.max_managed_by or 0),
        ai_outbound_call_count=int(plan.ai_outbound_call_count or 0),
        emergency_ai_call_count=int(plan.emergency_ai_call_count or 0),
        auto_renew=record.auto_renew,
    )


@user_router.post("/cancel")
async def cancel_membership(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await _get_active_membership(db, current_user.id)
    if not membership:
        raise HTTPException(status_code=404, detail="您当前没有有效的会员订阅")
    membership.status = "cancelled"
    membership.auto_renew = False
    await db.flush()
    return {"ok": True, "cancelled_id": membership.id}


# ──────────────── 用户端：收银台优惠计算（v1.1 二选一）────────────────


POINTS_DEDUCT_RATIO_CAP = 0.20


@user_router.post("/calculate-discount", response_model=DiscountCalcResponse)
async def calculate_discount(
    data: DiscountCalcRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, data.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    qty = max(int(data.quantity or 1), 1)
    unit_price = float(product.sale_price or 0)
    original_price = unit_price * qty

    membership = await _get_active_membership(db, current_user.id)
    plan: Optional[MembershipPlan] = membership.plan if membership else None
    is_paid_member = bool(plan)
    member_discount_eligible = bool(getattr(product, "is_member_discount_eligible", False))
    points_deductible = bool(getattr(product, "points_deductible", False))

    if data.user_points is not None:
        user_points = int(data.user_points)
    else:
        user_points = await _get_user_points_balance(db, current_user.id)

    options: list[DiscountOptionItem] = []

    if (
        member_discount_eligible and is_paid_member and plan
        and plan.discount_rate is not None and plan.discount_rate < 1.0
    ):
        member_final = round(original_price * float(plan.discount_rate), 2)
        member_discount_amount = round(original_price - member_final, 2)
        options.append(DiscountOptionItem(
            type="member_discount",
            label=f"付费会员折扣（{plan.name} {plan.discount_rate}）",
            discount_amount=member_discount_amount,
            final_price=member_final,
            detail=f"按 {plan.discount_rate} 折计算",
        ))

    points_to_yuan = 0.01
    if points_deductible and user_points > 0:
        cap = round(original_price * POINTS_DEDUCT_RATIO_CAP, 2)
        max_by_points = round(user_points * points_to_yuan, 2)
        deduct = round(min(cap, max_by_points), 2)
        if deduct > 0:
            used_points = int(round(deduct / points_to_yuan))
            options.append(DiscountOptionItem(
                type="points_deduction",
                label="积分抵扣（最多抵扣订单金额 20%）",
                discount_amount=deduct,
                final_price=round(original_price - deduct, 2),
                detail=f"使用 {used_points} 积分抵扣 ¥{deduct}",
                use_points=used_points,
            ))

    if not options:
        options.append(DiscountOptionItem(
            type="none",
            label="无可用优惠",
            discount_amount=0.0,
            final_price=round(original_price, 2),
            detail="按原价支付",
        ))
        recommended = "none"
    else:
        best = max(options, key=lambda x: x.discount_amount)
        recommended = best.type

    return DiscountCalcResponse(
        product_id=product.id,
        quantity=qty,
        original_price=round(original_price, 2),
        is_paid_member=is_paid_member,
        user_points=user_points,
        member_discount_eligible=member_discount_eligible,
        points_deductible=points_deductible,
        options=options,
        recommended=recommended,
    )
