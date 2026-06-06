"""[会员中心优化 PRD v2.0 2026-05-26]

新接口（在原有 /api/membership/* 基础上补充，不影响旧端兼容）：
- GET  /api/member/center                  会员中心一次性聚合（用户当前等级 + 配额 + 套餐 + 入口）
- POST /api/member/order                   创建会员购买订单（虚拟订单，复用 fulfillment_type='virtual'）
- POST /api/member/order/{id}/pay          发起支付（返回各端支付参数；当前为模拟实现）
- GET  /api/member/orders                  我的会员订单列表（Tab 筛选：全部/会员费/商品/积分）
- GET  /api/admin/users/{id}/membership    后台用户会员详情卡片
- POST /api/admin/users/{id}/membership/adjust  后台手动调整（延期/重置/降级）

业务规则（按 PRD §7 实现 grant_membership 升级/续费/降级）：
- 免费会员 → 直接开通付费
- 同套餐续费 → 时长追加（剩余 + 新周期）
- 跨套餐升级 → 立即生效 + 旧时长作废（仅允许升到更高 rank 的套餐）
- 降级 → 拒绝（提示"请等当前套餐到期"）
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub
from app.models.models import (
    FulfillmentType,
    OrderItem,
    UnifiedOrder,
    UnifiedOrderStatus,
    UnifiedPaymentMethod,
    User,
)


router = APIRouter(prefix="/api/member", tags=["会员中心-v2.0"])
admin_router = APIRouter(prefix="/api/admin/users", tags=["会员中心-v2.0-后台"])

admin_dep = require_role("admin")


# ─────────────────── 工具函数 ───────────────────


def _plan_rank(plan: MembershipPlan) -> float:
    """计算套餐档次：以年价为优先，否则月价 × 12。用于升级/降级判定。"""
    if plan.price_year is not None and float(plan.price_year) > 0:
        return float(plan.price_year)
    return float(plan.price_month or 0) * 12


def _days_for_period(period: str) -> int:
    return 365 if period == "year" else 30


async def _get_active_sub(db: AsyncSession, user_id: int) -> Optional[UserMembershipSub]:
    now = datetime.now()
    result = await db.execute(
        select(UserMembershipSub)
        .where(UserMembershipSub.user_id == user_id)
        .where(UserMembershipSub.status == "active")
        .where(UserMembershipSub.expire_at > now)
        .order_by(UserMembershipSub.expire_at.desc())
    )
    return result.scalars().first()


async def _grant_membership(
    db: AsyncSession,
    user_id: int,
    plan: MembershipPlan,
    period: str,
) -> UserMembershipSub:
    """开通/续费/升级会员资格（PRD §7.1）。

    返回新生效的 UserMembershipSub 记录。
    """
    days = _days_for_period(period)
    now = datetime.now()
    existing = await _get_active_sub(db, user_id)

    if existing is None:
        # 免费会员 → 开通付费
        start_at = now
        expire_at = now + timedelta(days=days)
    elif existing.plan_id == plan.id:
        # 同套餐续费 → 时长追加
        base = max(existing.expire_at, now)
        start_at = existing.start_at
        expire_at = base + timedelta(days=days)
        existing.status = "expired"  # 旧记录归档（追加版会写入新行）
    else:
        # 跨套餐升级（rank 已校验过）→ 立即生效，旧时长作废
        existing.status = "cancelled"
        start_at = now
        expire_at = now + timedelta(days=days)

    record = UserMembershipSub(
        user_id=user_id,
        plan_id=plan.id,
        billing_cycle="yearly" if period == "year" else "monthly",
        start_at=start_at,
        expire_at=expire_at,
        status="active",
        paid_amount=Decimal(str(plan.price_year if period == "year" else plan.price_month or 0)),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


def _plan_to_brief(p: MembershipPlan, recommended: bool = False) -> dict:
    # PRD v1.0：移除 plan_code、benefits_desc；is_recommended 改为读取套餐自身字段
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price_month": float(p.price_month) if p.price_month is not None and float(p.price_month) > 0 else None,
        "price_year": float(p.price_year) if p.price_year is not None and float(p.price_year) > 0 else None,
        "max_managed": int(p.max_managed or 0),
        "ai_outbound_call_count": int(p.ai_outbound_call_count or 0),
        "emergency_ai_call_count": int(p.emergency_ai_call_count or 0),
        "max_managed_by": int(p.max_managed_by or 0),
        "is_recommended": bool(p.is_recommended) or recommended,
        "sort_order": int(p.sort_order or 0),
    }


# ─────────────────── 用户端：会员中心聚合数据 ───────────────────


@router.get("/center")
async def get_member_center(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[v2.0 §6.1] 获取会员中心一次性聚合数据。"""
    sub = await _get_active_sub(db, current_user.id)
    quota = await db.get(FreeMemberQuota, 1)

    # 当前等级
    if sub and sub.plan:
        plan = sub.plan
        current = {
            "level": "paid",
            "plan_id": plan.id,
            "plan_name": plan.name,
            "billing_cycle": sub.billing_cycle,
            "expire_at": sub.expire_at.isoformat() if sub.expire_at else None,
            "expire_date": sub.expire_at.strftime("%Y-%m-%d") if sub.expire_at else None,
            "max_managed": int(plan.max_managed or 0),
            "ai_outbound_call_count": int(plan.ai_outbound_call_count or 0),
            "emergency_ai_call_count": int(plan.emergency_ai_call_count or 0),
            "max_managed_by": int(plan.max_managed_by or 0),
        }
        # 到期提醒（提前 7/3/1 天）
        days_left = (sub.expire_at - datetime.now()).days if sub.expire_at else None
        current["days_left"] = days_left
        current["expiring_soon"] = days_left is not None and 0 <= days_left <= 7
    else:
        current = {
            "level": "free",
            "plan_id": None,
            "plan_name": "免费会员",
            "billing_cycle": None,
            "expire_at": None,
            "expire_date": "长期",
            "max_managed": int(quota.max_managed) if quota else 3,
            "ai_outbound_call_count": int(quota.ai_outbound_call_count) if quota else 5,
            "emergency_ai_call_count": int(quota.emergency_ai_call_count) if quota else 3,
            "max_managed_by": int(quota.max_managed_by) if quota else 3,
            "days_left": None,
            "expiring_soon": False,
        }

    # 可购套餐（启用中），按 sort_order 排序，第一个为推荐
    plans_result = await db.execute(
        select(MembershipPlan)
        .where(MembershipPlan.is_active == True)  # noqa: E712
        .order_by(MembershipPlan.sort_order.asc(), MembershipPlan.id.asc())
    )
    plans = list(plans_result.scalars().all())
    plan_dicts = []
    for idx, p in enumerate(plans):
        plan_dicts.append(_plan_to_brief(p, recommended=(idx == 0 and current["level"] == "free")))

    # 当前套餐的 rank（用于前端判断展示"续费/升级/不可购"按钮）
    current_rank = _plan_rank(sub.plan) if sub and sub.plan else None

    # [优化 v1.0 2026-05-27] free_quota 永远是「免费会员额度配置」表中的全局额度，
    # 与当前登录用户档位无关。供 H5 权益对比表"免费会员"列消费。
    # 兜底：若 free_member_quota 记录不存在，返回 0/0/0。
    free_quota_resp = {
        "max_managed": int(quota.max_managed) if quota else 0,
        "ai_outbound_call_count": int(quota.ai_outbound_call_count) if quota else 0,
        "emergency_ai_call_count": int(quota.emergency_ai_call_count) if quota else 0,
    }

    return {
        "current": current,
        "plans": plan_dicts,
        "current_plan_rank": current_rank,
        "ranks": {p.id: _plan_rank(p) for p in plans},
        # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 权益卡片极简化：
        # - label 重命名为 PRD 规范主文案「家庭守护成员」
        # - value 直接是数据库 max_managed 原值（已含本人，迁移后），前端零加工原样展示
        # - unit 由「份（含本人）」改为「人」——副文案不再出现「含本人」字样
        # - 不再添加副文案行
        "benefits_cards": [
            {"key": "max_managed", "label": "家庭守护成员", "value": current["max_managed"], "unit": "人"},
            {"key": "ai_outbound_call_count", "label": "AI 外呼提醒", "value": current["ai_outbound_call_count"], "unit": "次/月"},
            {"key": "emergency_ai_call_count", "label": "紧急 AI 呼叫", "value": current["emergency_ai_call_count"], "unit": "次/月"},
            {"key": "placeholder", "label": "更多权益", "value": None, "unit": "敬请期待"},
        ],
        "free_quota": free_quota_resp,
    }


# ─────────────────── 用户端：可购套餐列表 ───────────────────


@router.get("/quota-usage")
async def get_member_quota_usage(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 会员中心『本月配额』使用量。

    返回当前用户本月已用的：AI 外呼提醒、紧急 AI 呼叫 次数；以及当前家庭档案数。

    [PRD-MEMBER-COUNT-CONSISTENCY-V1 2026-05-31 修复] 家庭档案数口径统一：
    - 旧逻辑使用裸 SQL `WHERE COALESCE(is_self,0)=0` 强制剔除本人，
      且未过滤软删除记录，导致与 /api/family/member/quota 两接口数字对不上
      （蓝卡片显示 3、配额卡却显示 6 等异常）。
    - 新逻辑改为调用公共方法 count_managed_family_members（含本人 + 排除软删除），
      与蓝卡片完全一致，从根上杜绝口径漂移。

    数据来源：
    - user_quota_usage 表（按月统计），缺失/无记录时返回 0
    - count_managed_family_members 公共方法（family_member_v2.py）
    """
    # 延迟导入避免循环依赖
    from app.api.family_member_v2 import count_managed_family_members

    used_outbound = 0
    used_emergency = 0
    used_managed = 0

    # 安全读 user_quota_usage：表/列可能不存在
    try:
        ym = datetime.now().strftime("%Y-%m")
        row = (
            await db.execute(
                text(
                    "SELECT ai_outbound_call_used, emergency_ai_call_used "
                    "FROM user_quota_usage "
                    "WHERE user_id = :uid AND period_month = :ym "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"uid": current_user.id, "ym": ym},
            )
        ).first()
        if row is not None:
            used_outbound = int(row[0] or 0)
            used_emergency = int(row[1] or 0)
    except Exception:
        pass

    # 家庭档案数：通过公共方法统计，与 /api/family/member/quota 完全一致
    try:
        used_managed = await count_managed_family_members(db, current_user.id)
    except Exception:
        pass

    return {
        "ai_outbound_call_used": used_outbound,
        "emergency_ai_call_used": used_emergency,
        "max_managed_used": used_managed,
        "period_month": datetime.now().strftime("%Y-%m"),
    }



@router.get("/plans")
async def list_member_plans(db: AsyncSession = Depends(get_db)):
    """[v2.0 §6.1] 获取所有启用中的付费套餐。"""
    plans_result = await db.execute(
        select(MembershipPlan)
        .where(MembershipPlan.is_active == True)  # noqa: E712
        .order_by(MembershipPlan.sort_order.asc(), MembershipPlan.id.asc())
    )
    plans = list(plans_result.scalars().all())
    return [_plan_to_brief(p, recommended=(idx == 0)) for idx, p in enumerate(plans)]


# ─────────────────── 用户端：创建会员订单 ───────────────────


class MemberOrderCreateRequest(BaseModel):
    plan_id: int
    period: str = Field(..., description="month 或 year")
    pay_channel: Optional[str] = Field(None, description="wechat_jsapi/alipay_wap/wechat_app/alipay_app；不传则按端默认")


def _generate_order_no() -> str:
    return "MEM" + datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()


@router.post("/order")
async def create_member_order(
    data: MemberOrderCreateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[v2.0 §6.3] 创建会员购买订单。"""
    if data.period not in ("month", "year"):
        raise HTTPException(400, "period 仅允许 month 或 year")

    plan = await db.get(MembershipPlan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(404, "套餐不存在或已下线")

    price = plan.price_year if data.period == "year" else plan.price_month
    if price is None or float(price) <= 0:
        raise HTTPException(400, f"套餐 {plan.name} 不支持{'年' if data.period == 'year' else '月'}付")

    # 跨套餐升降级校验
    existing = await _get_active_sub(db, current_user.id)
    if existing and existing.plan_id != plan.id:
        current_plan = existing.plan
        if _plan_rank(plan) <= _plan_rank(current_plan):
            raise HTTPException(400, "不允许降级到更低/同级套餐，请等当前套餐到期")

    # 生成订单
    order = UnifiedOrder(
        user_id=current_user.id,
        order_no=_generate_order_no(),
        total_amount=Decimal(str(price)),
        status=UnifiedOrderStatus.pending_payment,
        payment_channel_code=data.pay_channel or "wechat_jsapi",
        payment_display_name=f"[会员费] {plan.name}·{'年卡' if data.period == 'year' else '月卡'}",
        notes=f"[会员费] {plan.name}·{'年卡' if data.period == 'year' else '月卡'}",
        product_type="membership",
    )
    db.add(order)
    await db.flush()

    product_name = f"【会员费】{plan.name}·{'年卡' if data.period == 'year' else '月卡'}"
    item = OrderItem(
        order_id=order.id,
        product_id=None,  # 会员费订单无关联实物商品
        product_name=product_name,
        product_price=Decimal(str(price)),
        quantity=1,
        subtotal=Decimal(str(price)),
        fulfillment_type=FulfillmentType.virtual,
        membership_plan_id=plan.id,
        membership_period=data.period,
    )
    db.add(item)
    await db.flush()
    await db.refresh(order)

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "product_name": product_name,
        "amount": float(price),
        "plan_id": plan.id,
        "plan_name": plan.name,
        "period": data.period,
        "pay_channel": order.payment_channel_code,
        "status": "pending",
    }


# ─────────────────── 用户端：发起支付（模拟） ───────────────────


class MemberOrderPayRequest(BaseModel):
    pay_channel: Optional[str] = None
    # 测试用：simulate=true 时直接走支付成功回调
    simulate: bool = True


@router.post("/order/{order_id}/pay")
async def pay_member_order(
    order_id: int,
    data: MemberOrderPayRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[v2.0 §6.3] 发起支付。当前实现为模拟支付（simulate=True 时直接置 paid 并 grant_membership）。"""
    order = await db.get(UnifiedOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "订单不存在")
    if order.status != UnifiedOrderStatus.pending_payment:
        raise HTTPException(400, f"订单当前状态为 {order.status}，无法支付")

    # 取出会员订单条目
    item_q = await db.execute(
        select(OrderItem)
        .where(OrderItem.order_id == order.id)
        .where(OrderItem.membership_plan_id.isnot(None))
    )
    item = item_q.scalars().first()
    if not item or item.membership_plan_id is None or not item.membership_period:
        raise HTTPException(400, "订单不是会员费订单")

    plan = await db.get(MembershipPlan, item.membership_plan_id)
    if not plan:
        raise HTTPException(404, "会员套餐不存在")

    if data.pay_channel:
        order.payment_channel_code = data.pay_channel

    if data.simulate:
        # 模拟支付成功：直接 grant
        sub = await _grant_membership(db, current_user.id, plan, item.membership_period)
        order.status = UnifiedOrderStatus.completed
        order.paid_at = datetime.now()
        order.paid_amount = order.total_amount
        await db.flush()
        return {
            "ok": True,
            "paid": True,
            "order_id": order.id,
            "sub_id": sub.id,
            "expire_at": sub.expire_at.isoformat(),
            "plan_name": plan.name,
        }

    # 真实通道未接入：返回 stub 支付参数
    return {
        "ok": True,
        "paid": False,
        "order_id": order.id,
        "pay_channel": order.payment_channel_code,
        "pay_params": {
            "stub": True,
            "msg": "请在管理后台「支付配置」菜单完成真实通道接入后再使用",
        },
    }


# ─────────────────── 用户端：会员订单列表（含 Tab 筛选） ───────────────────


@router.get("/orders")
async def list_my_member_orders(
    tab: str = Query("membership", description="all/membership/product/points"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[v2.0 §3.3] 我的会员订单（金色卡片样式所需数据）。"""
    stmt = (
        select(UnifiedOrder, OrderItem)
        .join(OrderItem, OrderItem.order_id == UnifiedOrder.id)
        .where(UnifiedOrder.user_id == current_user.id)
        .order_by(UnifiedOrder.created_at.desc())
    )
    if tab == "membership":
        stmt = stmt.where(OrderItem.membership_plan_id.isnot(None))
    elif tab == "product":
        stmt = stmt.where(OrderItem.fulfillment_type != FulfillmentType.virtual)
    # tab=all 不加条件；tab=points 走积分商城另有接口

    result = await db.execute(stmt)
    items = []
    for order, oi in result.all():
        items.append({
            "order_id": order.id,
            "order_no": order.order_no,
            "product_name": oi.product_name,
            "amount": float(order.total_amount or 0),
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "is_membership": oi.membership_plan_id is not None,
            "membership_plan_id": oi.membership_plan_id,
            "membership_period": oi.membership_period,
            "fulfillment_type": oi.fulfillment_type.value if hasattr(oi.fulfillment_type, "value") else str(oi.fulfillment_type),
        })
    return {"tab": tab, "items": items, "total": len(items)}


# ─────────────────── 管理后台：用户会员详情 ───────────────────


@admin_router.get("/{user_id}/membership")
async def admin_get_user_membership(
    user_id: int,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[v2.0 §4.4] 后台用户管理详情页会员信息卡片。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    sub = await _get_active_sub(db, user_id)
    quota = await db.get(FreeMemberQuota, 1)

    if sub and sub.plan:
        plan = sub.plan
        return {
            "user_id": user_id,
            "membership_level": "paid",
            "plan_id": plan.id,
            "plan_name": plan.name,
            "expire_at": sub.expire_at.isoformat() if sub.expire_at else None,
            "max_managed": int(plan.max_managed or 0),
            "max_managed_by": int(plan.max_managed_by or 0),
            "ai_outbound_call_count": int(plan.ai_outbound_call_count or 0),
            "emergency_ai_call_count": int(plan.emergency_ai_call_count or 0),
            "sub_id": sub.id,
            "billing_cycle": sub.billing_cycle,
        }

    return {
        "user_id": user_id,
        "membership_level": "free",
        "plan_id": None,
        "plan_name": "免费会员",
        "expire_at": None,
        "max_managed": int(quota.max_managed) if quota else 3,
        "max_managed_by": int(quota.max_managed_by) if quota else 3,
        "ai_outbound_call_count": int(quota.ai_outbound_call_count) if quota else 5,
        "emergency_ai_call_count": int(quota.emergency_ai_call_count) if quota else 3,
        "sub_id": None,
        "billing_cycle": None,
    }


class AdminMembershipAdjust(BaseModel):
    action: str = Field(..., description="extend / downgrade / reset_quota")
    days: Optional[int] = Field(None, description="action=extend 时延长的天数")


@admin_router.post("/{user_id}/membership/adjust")
async def admin_adjust_membership(
    user_id: int,
    data: AdminMembershipAdjust,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[v2.0 §4.4] 后台手动调整：延期 / 降级 / 重置额度。"""
    sub = await _get_active_sub(db, user_id)
    if data.action == "extend":
        if not sub:
            raise HTTPException(400, "用户当前为免费会员，无法延期")
        days = int(data.days or 30)
        sub.expire_at = sub.expire_at + timedelta(days=days)
        await db.flush()
        return {"ok": True, "action": "extend", "new_expire_at": sub.expire_at.isoformat()}
    if data.action == "downgrade":
        if not sub:
            return {"ok": True, "action": "downgrade", "already_free": True}
        sub.status = "cancelled"
        await db.flush()
        return {"ok": True, "action": "downgrade", "sub_id": sub.id}
    if data.action == "reset_quota":
        # 简化实现：仅 ok，真实重置逻辑在 user_quota_usage 表中（已在 PRD v1.2 实现）
        return {"ok": True, "action": "reset_quota"}
    raise HTTPException(400, f"未知 action: {data.action}")


# ─────────────────── 定时任务：到期降级 + 额度重置 ───────────────────


async def membership_expire_job(db: AsyncSession) -> dict:
    """[v2.0 §8.1] 每日 03:00 到期降级任务。

    将所有 expire_at <= now 且 status='active' 的订阅置为 expired。
    """
    now = datetime.now()
    result = await db.execute(
        select(UserMembershipSub)
        .where(UserMembershipSub.status == "active")
        .where(UserMembershipSub.expire_at <= now)
    )
    expired = list(result.scalars().all())
    for sub in expired:
        sub.status = "expired"
    await db.flush()
    return {"expired_count": len(expired), "ran_at": now.isoformat()}


async def membership_remind_job(db: AsyncSession) -> dict:
    """[v2.0 §8.2] 每日 10:00 到期提醒任务（提前 7/3/1 天）。

    实际推送通道（站内/微信/横幅）由通知服务负责，本任务仅返回需要提醒的用户列表。
    """
    now = datetime.now()
    reminders = []
    for days_before in (7, 3, 1):
        target_lo = now + timedelta(days=days_before)
        target_lo = target_lo.replace(hour=0, minute=0, second=0, microsecond=0)
        target_hi = target_lo + timedelta(days=1)
        result = await db.execute(
            select(UserMembershipSub)
            .where(UserMembershipSub.status == "active")
            .where(UserMembershipSub.expire_at >= target_lo)
            .where(UserMembershipSub.expire_at < target_hi)
        )
        for sub in result.scalars().all():
            reminders.append({
                "user_id": sub.user_id,
                "days_before": days_before,
                "expire_at": sub.expire_at.isoformat(),
            })
    return {"reminders": reminders, "ran_at": now.isoformat()}


# 暴露管理调试入口（无 admin 限制，但是手动触发的便利接口，可由 cron 直连）
@router.post("/_internal/cron/expire")
async def cron_expire(db: AsyncSession = Depends(get_db)):
    """[v2.0 §8.1] 内部 cron 调度入口：到期降级。"""
    return await membership_expire_job(db)


@router.post("/_internal/cron/remind")
async def cron_remind(db: AsyncSession = Depends(get_db)):
    """[v2.0 §8.2] 内部 cron 调度入口：到期提醒。"""
    return await membership_remind_job(db)
