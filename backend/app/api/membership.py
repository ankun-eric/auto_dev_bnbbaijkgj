"""[付费会员体系 PRD v1.1] 付费会员套餐 + 用户订阅 + 收银台优惠计算 API。

面向 3 类调用方：
1. 后台管理（/api/admin/membership/*）：套餐 CRUD、免费额度配置
2. 用户端查询（/api/membership/*）：可购买套餐、当前会员状态、订阅、优惠计算
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
from app.models.models import PointsRecord, PointsType, Product, User
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
        "plan_code": p.plan_code,
        "name": p.name,
        "price_monthly": float(p.price_monthly or 0),
        "price_yearly": float(p.price_yearly) if p.price_yearly is not None else None,
        "ai_call_quota": int(p.ai_call_quota or 0),
        "ai_alert_quota": int(p.ai_alert_quota or 0),
        "ai_remind_quota": int(p.ai_remind_quota or 0),
        "emergency_ai_call_count": int(getattr(p, "emergency_ai_call_count", 0) or 0),
        "max_guardians": int(p.max_guardians or 1),
        "max_managed": int(getattr(p, "max_managed", 10) or 10),
        "point_multiplier": float(getattr(p, "point_multiplier", 1.0) or 1.0),
        "discount_rate": float(p.discount_rate or 1.0),
        "benefits_desc": p.benefits_desc,
        "is_active": bool(p.is_active),
        "sort_order": int(p.sort_order or 0),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
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
    """根据 PointsRecord 求和得到用户当前积分余额。"""
    records = await db.execute(
        select(PointsRecord).where(PointsRecord.user_id == user_id)
    )
    total = 0
    for r in records.scalars().all():
        # 收入为正，支出为负
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
    exists = await db.execute(select(MembershipPlan).where(MembershipPlan.plan_code == data.plan_code))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail=f"套餐编码已存在：{data.plan_code}")
    plan = MembershipPlan(
        plan_code=data.plan_code,
        name=data.name,
        price_monthly=Decimal(str(data.price_monthly)),
        price_yearly=Decimal(str(data.price_yearly)) if data.price_yearly is not None else None,
        ai_call_quota=int(data.ai_call_quota or 0),
        ai_alert_quota=int(data.ai_alert_quota or 0),
        ai_remind_quota=int(data.ai_remind_quota or 0),
        emergency_ai_call_count=int(getattr(data, "emergency_ai_call_count", 0) or 0),
        max_guardians=int(data.max_guardians or 1),
        max_managed=int(getattr(data, "max_managed", 10) or 10),
        point_multiplier=float(getattr(data, "point_multiplier", 1.0) or 1.0),
        discount_rate=float(data.discount_rate or 1.0),
        benefits_desc=data.benefits_desc,
        is_active=bool(data.is_active),
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
    if "plan_code" in update_data and update_data["plan_code"] != plan.plan_code:
        ex = await db.execute(
            select(MembershipPlan).where(MembershipPlan.plan_code == update_data["plan_code"])
        )
        if ex.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail=f"套餐编码已存在：{update_data['plan_code']}")
    for k, v in update_data.items():
        if k in ("price_monthly", "price_yearly") and v is not None:
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
    plan = await db.get(MembershipPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    # 已购用户继续享受到期；这里仅置为 is_active=False（软下线）
    plan.is_active = False
    await db.flush()
    return {"ok": True, "soft_deleted": True}


# ──────────────── 后台：免费额度配置 ────────────────


@admin_router.get("/free-quota", response_model=FreeMemberQuotaResponse)
async def admin_get_free_quota(
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    quota = await db.get(FreeMemberQuota, 1)
    if not quota:
        quota = FreeMemberQuota(id=1)
        db.add(quota)
        await db.flush()
        await db.refresh(quota)
    return quota


@admin_router.put("/free-quota", response_model=FreeMemberQuotaResponse)
async def admin_update_free_quota(
    data: FreeMemberQuotaUpdate,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    quota = await db.get(FreeMemberQuota, 1)
    if not quota:
        quota = FreeMemberQuota(id=1)
        db.add(quota)
        await db.flush()
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(quota, k, v)
    await db.flush()
    await db.refresh(quota)
    return quota


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
            plan_code=plan.plan_code,
            plan_name=plan.name,
            expire_at=membership.expire_at,
            discount_rate=float(plan.discount_rate or 1.0),
            max_guardians=int(plan.max_guardians or 1),
            max_managed=int(getattr(plan, "max_managed", 10) or 10),
            ai_call_quota=int(plan.ai_call_quota or 0),
            ai_alert_quota=int(plan.ai_alert_quota or 0),
            ai_remind_quota=int(plan.ai_remind_quota or 0),
            emergency_ai_call_count=int(getattr(plan, "emergency_ai_call_count", 0) or 0),
            benefits_desc=plan.benefits_desc,
        )

    # 没有有效订阅 → 走免费额度
    quota = await db.get(FreeMemberQuota, 1)
    return MembershipMeResponse(
        is_paid_member=False,
        plan_id=None,
        plan_code=None,
        plan_name="普通会员",
        expire_at=None,
        discount_rate=1.0,
        max_guardians=int(quota.max_guardians) if quota else 1,
        max_managed=int(getattr(quota, "max_managed", 3)) if quota else 3,
        ai_call_quota=int(quota.ai_call_quota) if quota else 0,
        ai_alert_quota=int(quota.ai_alert_quota) if quota else 3,
        ai_remind_quota=int(quota.ai_remind_quota) if quota else 0,
        emergency_ai_call_count=int(getattr(quota, "emergency_ai_call_count", 3)) if quota else 3,
        benefits_desc=quota.benefits_desc if quota else None,
    )


# ──────────────── 用户端：订阅（模拟付款）────────────────


@user_router.post("/subscribe", response_model=UserMembershipResponse)
async def subscribe_plan(
    data: MembershipSubscribeRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户订阅 / 续费会员套餐。

    本接口为简化版：直接创建一条 active 的 UserMembershipSub 记录。
    真实生产环境应先调起支付，支付回调后再创建（参考已有 alipay_notify 流程）。
    PRD v1.1 § 九：套餐购买/续费**不允许**积分抵扣。
    """
    plan = await db.get(MembershipPlan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="套餐不存在或已下线")
    if data.billing_cycle not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="billing_cycle 仅允许 monthly/yearly")

    price = plan.price_monthly if data.billing_cycle == "monthly" else (plan.price_yearly or plan.price_monthly)

    now = datetime.utcnow()
    # 续费规则：若当前已有 active，从 expire_at 接续；否则从现在开始
    existing = await _get_active_membership(db, current_user.id)
    start_at = existing.expire_at if existing else now
    if existing:
        existing.status = "expired"  # 旧记录归档
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
        plan_code=plan.plan_code,
        billing_cycle=record.billing_cycle,
        start_at=record.start_at,
        expire_at=record.expire_at,
        status=record.status,
        discount_rate=float(plan.discount_rate or 1.0),
        max_guardians=int(plan.max_guardians or 1),
        ai_call_quota=int(plan.ai_call_quota or 0),
        ai_alert_quota=int(plan.ai_alert_quota or 0),
        ai_remind_quota=int(plan.ai_remind_quota or 0),
        auto_renew=record.auto_renew,
    )


@user_router.post("/cancel")
async def cancel_membership(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户主动取消订阅：立即降级为免费会员。"""
    membership = await _get_active_membership(db, current_user.id)
    if not membership:
        raise HTTPException(status_code=404, detail="您当前没有有效的会员订阅")
    membership.status = "cancelled"
    membership.auto_renew = False
    await db.flush()
    return {"ok": True, "cancelled_id": membership.id}


# ──────────────── 用户端：收银台优惠计算（v1.1 二选一）────────────────


# v1.1 § 五：单笔订单积分抵扣上限 = 订单金额的 20%
POINTS_DEDUCT_RATIO_CAP = 0.20


@user_router.post("/calculate-discount", response_model=DiscountCalcResponse)
async def calculate_discount(
    data: DiscountCalcRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """收银台计算可用优惠（PRD v1.1 § 五 / 附录 A.4）：
    - 会员折扣（is_member_discount_eligible + 用户为付费会员）
    - 积分抵扣（points_deductible），单笔最多抵扣 20%
    - 二选一不可叠加
    - 默认推荐力度更大的一项
    """
    product = await db.get(Product, data.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    qty = max(int(data.quantity or 1), 1)
    unit_price = float(product.sale_price or 0)
    original_price = unit_price * qty

    # 会员状态
    membership = await _get_active_membership(db, current_user.id)
    plan: Optional[MembershipPlan] = membership.plan if membership else None
    is_paid_member = bool(plan)
    member_discount_eligible = bool(getattr(product, "is_member_discount_eligible", False))
    points_deductible = bool(getattr(product, "points_deductible", False))

    # 积分余额（优先使用请求传入，便于测试）
    if data.user_points is not None:
        user_points = int(data.user_points)
    else:
        user_points = await _get_user_points_balance(db, current_user.id)

    options: list[DiscountOptionItem] = []

    # 会员折扣选项
    member_discount_amount = 0.0
    if member_discount_eligible and is_paid_member and plan and plan.discount_rate < 1.0:
        member_final = round(original_price * float(plan.discount_rate), 2)
        member_discount_amount = round(original_price - member_final, 2)
        options.append(DiscountOptionItem(
            type="member_discount",
            label=f"付费会员折扣（{plan.name} {plan.discount_rate}）",
            discount_amount=member_discount_amount,
            final_price=member_final,
            detail=f"按 {plan.discount_rate} 折计算",
        ))

    # 积分抵扣选项 —— 兑换比例沿用代码现状：
    # 现有 PointsMallItem.price_points 体系下，1 积分≈1 分钱（即 100 积分=1 元）
    # 这里取 1 积分 = 0.01 元为代码现状的兑换比例。
    points_to_yuan = 0.01
    points_deduct_amount = 0.0
    used_points = 0
    if points_deductible and user_points > 0:
        cap = round(original_price * POINTS_DEDUCT_RATIO_CAP, 2)  # 20% 上限
        max_by_points = round(user_points * points_to_yuan, 2)
        deduct = min(cap, max_by_points)
        deduct = round(deduct, 2)
        if deduct > 0:
            used_points = int(round(deduct / points_to_yuan))
            points_deduct_amount = deduct
            options.append(DiscountOptionItem(
                type="points_deduction",
                label=f"积分抵扣（最多抵扣订单金额 20%）",
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
        # 默认推荐：力度大的（折扣金额最大）
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
