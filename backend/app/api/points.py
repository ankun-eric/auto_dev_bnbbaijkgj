from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    HealthProfile,
    MemberLevel,
    PointsExchange,
    PointsMallItem,
    PointsRecord,
    PointsType,
    SignInRecord,
    SystemConfig,
    UnifiedOrder,
    UnifiedOrderStatus,
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


# ─── Bug #4 修复：权威"可用积分"计算 ───

# 被视为"获得类"的 PointsType（正向增量）
_EARN_TYPES = {
    PointsType.signin,
    PointsType.task,
    PointsType.invite,
    PointsType.purchase,
    PointsType.checkin,
    PointsType.completeProfile,
}

# 被视为"消费类"的 PointsType（负向扣减）
_CONSUME_TYPES = {
    PointsType.redeem,
    PointsType.deduct,
}


async def compute_available_points(db: AsyncSession, user_id: int) -> dict:
    """Bug #4 修复口径：
        可用积分 = 累计获得 − 已消耗 − 已过期 − 已冻结

    实现说明：
    - 当前 PointsRecord 没有 status 字段，也没有 expire 枚举值。
      本函数采用"金额符号优先、类型白名单兜底"的方式，对未来新增 expire/frozen 字段/类型保持前向兼容：
        * 累计获得 earned   = 所有 amount > 0 的流水合计（主要来源：signin/task/invite/purchase/checkin/completeProfile）
        * 已消耗 consumed  = 所有 amount < 0 且 type ∈ {redeem, deduct}（或未来的 consume/exchange）的流水合计（取绝对值）
        * 已过期 expired   = type 名为 'expire' 的流水合计（当前枚举未定义，兼容以字符串比对方式识别）
        * 已冻结 frozen    = status == 'frozen' 的流水合计（当前无此字段，默认 0）
    - 返回 earned/consumed/expired/frozen/available 五项，available = earned − consumed − expired − frozen，底为 0。
    """
    # 累计获得：金额为正
    earned_res = await db.execute(
        select(func.coalesce(func.sum(PointsRecord.points), 0)).where(
            PointsRecord.user_id == user_id,
            PointsRecord.points > 0,
        )
    )
    earned = int(earned_res.scalar() or 0)

    # 已消耗：金额为负（取绝对值）
    consumed_res = await db.execute(
        select(func.coalesce(func.sum(PointsRecord.points), 0)).where(
            PointsRecord.user_id == user_id,
            PointsRecord.points < 0,
        )
    )
    consumed_signed = int(consumed_res.scalar() or 0)
    consumed = abs(consumed_signed)

    # 已过期：按 type 名称兼容识别（当前枚举无 'expire'，future-proof）
    expired = 0
    try:
        expired_res = await db.execute(
            select(func.coalesce(func.sum(func.abs(PointsRecord.points)), 0)).where(
                PointsRecord.user_id == user_id,
                PointsRecord.type == "expire",
            )
        )
        expired = int(expired_res.scalar() or 0)
    except Exception:
        expired = 0

    # 已冻结：PointsRecord 当前无 status 字段，占位 0；future-proof。
    frozen = 0
    if hasattr(PointsRecord, "status"):
        try:
            frozen_res = await db.execute(
                select(func.coalesce(func.sum(func.abs(PointsRecord.points)), 0)).where(
                    PointsRecord.user_id == user_id,
                    getattr(PointsRecord, "status") == "frozen",
                )
            )
            frozen = int(frozen_res.scalar() or 0)
        except Exception:
            frozen = 0

    available = earned - consumed - expired - frozen
    if available < 0:
        available = 0

    return {
        "earned": earned,
        "consumed": consumed,
        "expired": expired,
        "frozen": frozen,
        "available": available,
    }


@router.get("/balance")
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bug #4 修复：返回基于流水计算的权威可用积分，不修改 user.points 缓存字段。"""
    breakdown = await compute_available_points(db, current_user.id)
    return {
        "points": breakdown["available"],
        "available_points": breakdown["available"],
        "member_level": current_user.member_level,
        "breakdown": breakdown,
    }


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


# ---- 兼容前端可能使用的 /sign-in 路由 ----
@router.post("/sign-in", response_model=SignInResponse)
async def sign_in_alias(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sign_in(current_user=current_user, db=db)


# ---- 积分页所需汇总接口 ----
async def _get_config_int(db: AsyncSession, key: str, default: int = 0) -> int:
    res = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    cfg = res.scalar_one_or_none()
    if not cfg or cfg.config_value is None:
        return default
    try:
        return int(cfg.config_value)
    except (ValueError, TypeError):
        return default


@router.get("/summary")
async def get_points_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """积分页顶部所需数据：总积分 / 今日已获得积分 / 今日是否已签到 / 连续签到天数"""
    today = date.today()

    today_earned_res = await db.execute(
        select(func.coalesce(func.sum(PointsRecord.points), 0)).where(
            PointsRecord.user_id == current_user.id,
            PointsRecord.points > 0,
            func.date(PointsRecord.created_at) == today,
        )
    )
    today_earned = int(today_earned_res.scalar() or 0)

    sign_today_res = await db.execute(
        select(SignInRecord).where(
            SignInRecord.user_id == current_user.id,
            SignInRecord.sign_date == today,
        )
    )
    sign_today_record = sign_today_res.scalar_one_or_none()

    last_sign_res = await db.execute(
        select(SignInRecord)
        .where(SignInRecord.user_id == current_user.id)
        .order_by(SignInRecord.sign_date.desc())
        .limit(1)
    )
    last = last_sign_res.scalar_one_or_none()
    sign_days = 0
    if last:
        if last.sign_date == today or last.sign_date == today - timedelta(days=1):
            sign_days = last.consecutive_days

    breakdown = await compute_available_points(db, current_user.id)

    return {
        "total_points": breakdown["available"],
        "available_points": breakdown["available"],
        "today_earned_points": today_earned,
        "signed_today": sign_today_record is not None,
        "sign_days": sign_days,
        "breakdown": breakdown,
    }


ONCE_TASK_HIDE_AFTER_DAYS = 7  # 一次性任务完成 N 天后从列表中过滤掉


@router.get("/tasks")
async def list_daily_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """积分页日常任务清单。

    一次性任务（once）：
      - 完成后追加 status=completed + completed_at（ISO8601 字符串）
      - 完成超过 ONCE_TASK_HIDE_AFTER_DAYS 天的不再返回（前端列表自动消失）

    单条任务的查询失败时降级为 completed=False，整体接口始终返回 200。
    """
    try:
        today = date.today()
        now_dt = datetime.utcnow()

        def _iso(dt):
            try:
                return dt.isoformat() if dt else None
            except Exception:
                return None

        async def _safe_int_config(key: str, default: int) -> int:
            try:
                return await _get_config_int(db, key, default)
            except Exception:
                return default

        # 1. 每日签到
        sign_today = False
        try:
            sign_res = await db.execute(
                select(SignInRecord).where(
                    SignInRecord.user_id == current_user.id,
                    SignInRecord.sign_date == today,
                )
            )
            sign_today = sign_res.scalar_one_or_none() is not None
        except Exception:
            sign_today = False
        sign_points = await _safe_int_config("dailySignIn", 5)

        # 2. 健康打卡（今日是否已发放过 checkin 类型积分记录）
        health_checkin_done = False
        try:
            checkin_today_res = await db.execute(
                select(func.count(PointsRecord.id)).where(
                    PointsRecord.user_id == current_user.id,
                    PointsRecord.type == PointsType.checkin,
                    func.date(PointsRecord.created_at) == today,
                )
            )
            health_checkin_done = (checkin_today_res.scalar() or 0) > 0
        except Exception:
            health_checkin_done = False
        health_checkin_points = await _safe_int_config("healthCheckIn", 2)

        # 3. 完善健康档案（终身一次）
        fields_filled = False
        profile_awarded = False
        profile_completed_at = None
        try:
            profile_res = await db.execute(
                select(HealthProfile).where(HealthProfile.user_id == current_user.id)
            )
            profile = profile_res.scalar_one_or_none()
            fields_filled = bool(
                profile
                and profile.gender is not None
                and profile.birthday is not None
                and profile.height is not None
                and profile.weight is not None
            )
            completed_profile_award_res = await db.execute(
                select(PointsRecord)
                .where(
                    PointsRecord.user_id == current_user.id,
                    PointsRecord.type == PointsType.completeProfile,
                )
                .order_by(PointsRecord.created_at.asc())
                .limit(1)
            )
            profile_award_row = completed_profile_award_res.scalar_one_or_none()
            profile_awarded = profile_award_row is not None
            profile_completed_at = profile_award_row.created_at if profile_award_row else None
        except Exception:
            fields_filled = False
            profile_awarded = False
            profile_completed_at = None
        complete_profile_points = await _safe_int_config("completeProfile", 100)

        # 4. 首次下单（是否有任意已支付订单 —— 含到店核销前等所有支付后状态）
        first_order_done = False
        first_order_completed_at = None
        try:
            paid_statuses = [
                UnifiedOrderStatus.pending_shipment,
                UnifiedOrderStatus.pending_receipt,
                UnifiedOrderStatus.pending_use,
                UnifiedOrderStatus.pending_review,
                UnifiedOrderStatus.completed,
            ]
            paid_order_res = await db.execute(
                select(UnifiedOrder)
                .where(
                    UnifiedOrder.user_id == current_user.id,
                    UnifiedOrder.status.in_(paid_statuses),
                )
                .order_by(UnifiedOrder.id.asc())
                .limit(1)
            )
            paid_order_row = paid_order_res.scalar_one_or_none()
            first_order_done = paid_order_row is not None
            if paid_order_row is not None:
                first_order_completed_at = (
                    paid_order_row.paid_at
                    or paid_order_row.completed_at
                    or paid_order_row.received_at
                )
        except Exception:
            first_order_done = False
            first_order_completed_at = None
        first_order_points = await _safe_int_config("firstOrder", 100)

        # 5. 评价订单（有无待评价订单）—— UnifiedOrder.has_reviewed 字段在旧库可能不存在
        pending_review_count = 0
        try:
            pending_review_res = await db.execute(
                select(func.count(UnifiedOrder.id)).where(
                    UnifiedOrder.user_id == current_user.id,
                    UnifiedOrder.status == UnifiedOrderStatus.completed,
                    (UnifiedOrder.has_reviewed.is_(False)) | (UnifiedOrder.has_reviewed.is_(None)),
                )
            )
            pending_review_count = pending_review_res.scalar() or 0
        except Exception:
            pending_review_count = 0
        review_points = await _safe_int_config("reviewService", 10)

        # 6. 邀请好友（累计成功邀请人数）
        invited_count = 0
        try:
            invited_count_res = await db.execute(
                select(func.count(User.id)).where(User.referrer_no == current_user.user_no)
            )
            invited_count = invited_count_res.scalar() or 0
        except Exception:
            invited_count = 0
        invite_points = await _safe_int_config("inviteFriend", 100)

        tasks = [
            {
                "key": "daily_signin",
                "title": "每日签到",
                "subtitle": "每日可获得签到积分",
                "points": sign_points,
                "category": "daily",
                "completed": sign_today,
                "status": "completed" if sign_today else "pending",
                "action_type": "sign_in",
                "route": "/points",
            },
            {
                "key": "health_checkin",
                "title": "健康打卡",
                "subtitle": "完成今日健康打卡",
                "points": health_checkin_points,
                "category": "daily",
                "completed": health_checkin_done,
                "status": "completed" if health_checkin_done else "pending",
                "action_type": "navigate",
                "route": "/health-plan",
            },
            {
                # Bug #7 修复：跳转统一为 /health-profile（查看页，页内自带编辑入口），
                # 不再区分"已完善/未完善"。
                "key": "complete_profile",
                "title": "完善健康档案",
                "subtitle": "需填写：性别、出生日期、身高、体重",
                "points": complete_profile_points,
                "category": "once",
                "completed": profile_awarded,
                "status": "completed" if profile_awarded else "pending",
                "completed_at": _iso(profile_completed_at),
                "fields_filled": fields_filled,
                "action_type": "navigate",
                "route": "/health-profile",
                "target_url": "/health-profile",
                "enabled": True,
            },
            {
                # Bug #8 修复：任务配置保留但置为下线状态（enabled=False）。
                # 接口层过滤掉 enabled == False 的项，确保前端拿不到"首次下单"。
                # 已发放的首单积分不回收；_check_first_order 等既有判定逻辑保留不动。
                "key": "first_order",
                "title": "首次下单",
                "subtitle": "完成首笔订单（含到店核销前）",
                "points": first_order_points,
                "category": "once",
                "completed": first_order_done,
                "status": "completed" if first_order_done else "pending",
                "completed_at": _iso(first_order_completed_at),
                "action_type": "navigate",
                "route": "/services",
                "enabled": False,
            },
            {
                "key": "review_order",
                "title": "评价订单",
                "subtitle": (f"您有 {pending_review_count} 个待评价订单" if pending_review_count else "去评价已完成的订单"),
                "points": review_points,
                "category": "repeatable",
                "completed": False,
                "status": "pending",
                "pending_count": pending_review_count,
                "action_type": "navigate",
                "route": "/unified-orders?tab=pending_review",
            },
            {
                "key": "invite_friend",
                "title": "邀请好友",
                "subtitle": (f"已成功邀请 {invited_count} 位好友" if invited_count else "邀请好友注册得积分"),
                "points": invite_points,
                "category": "repeatable",
                "completed": False,
                "status": "pending",
                "invited_count": invited_count,
                "action_type": "navigate",
                "route": "/invite",
            },
        ]

        # 一次性任务完成超过 N 天则不再返回（前端列表自动消失）
        hide_threshold = now_dt - timedelta(days=ONCE_TASK_HIDE_AFTER_DAYS)
        filtered = []
        for t in tasks:
            # Bug #8 修复：接口层过滤掉 enabled == False 的任务（配置保留便于后续恢复）
            if t.get("enabled") is False:
                continue
            if t.get("category") == "once" and t.get("status") == "completed":
                ca_iso = t.get("completed_at")
                ca_dt = None
                if ca_iso:
                    try:
                        ca_dt = datetime.fromisoformat(ca_iso)
                    except Exception:
                        ca_dt = None
                if ca_dt is not None and ca_dt < hide_threshold:
                    continue
            filtered.append(t)
        return {"items": filtered}
    except Exception:
        return {"items": []}


@router.get("/level")
async def get_member_levels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MemberLevel).order_by(MemberLevel.min_points.asc()))
    items = [MemberLevelResponse.model_validate(l) for l in result.scalars().all()]
    return {"items": items}
