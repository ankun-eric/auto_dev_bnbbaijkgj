"""订单状态自动推进 + 提醒任务

[PRD 订单状态机简化方案 v1.0]（2026-05-03 起生效）：
- 下线 R1（appointed → pending_use 翻转）：现在用户填预约日 → 直接进入 pending_use，
  不需要再用定时器翻转。
- 保留 R2（次日 00:00 把未核销 pending_use 退回 pending_appointment 并清空 appointment_time）：
  防止用户白预约白跑后订单卡死，仍按次日 00:00 起每分钟扫描兜底。
- 旧的 5 个赴约提醒节点继续保留，新增「T-1 18:00 到店提醒」节点。
- 老的"您的订单已到核销时间（0 点触发）"通知整条下线（原本是 R1 翻转副产品，已随 R1 一起下线）。

实现要点：
1. 状态翻转 + 通知入库放在同一事务中，避免不一致
2. 每个推送节点借助 NotificationLog 去重，幂等可重放
3. 提供 `lazy_progress_order` 给 unified_orders 接口侧调用，作为定时器漏跑的实时兜底（仅 R2）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, time as dtime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session
from app.models.models import (
    Notification,
    NotificationLog,
    NotificationType,
    OrderItem,
    Product,
    UnifiedOrder,
    UnifiedOrderStatus,
)


logger = logging.getLogger(__name__)


# ──────────────── R2：次日兜底退回 ────────────────


async def run_r2_flip_back_to_appointment(session: Optional[AsyncSession] = None) -> int:
    """R2：次日 00:00 兜底回退（保留）。

    把所有 status=pending_use 且 OrderItem.appointment_time 的日期 < 今天且未核销的订单
    清空 appointment_time、status 退回 pending_appointment。返回受影响订单数。
    """
    own_session = session is None
    if own_session:
        session = async_session()  # type: ignore[assignment]
    try:
        if own_session:
            await session.__aenter__()  # type: ignore[union-attr]
        affected = await _do_r2(session)  # type: ignore[arg-type]
        if own_session:
            await session.commit()  # type: ignore[union-attr]
        return affected
    except Exception:
        if own_session:
            await session.rollback()  # type: ignore[union-attr]
        logger.exception("R2 flip failed")
        return 0
    finally:
        if own_session:
            try:
                await session.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass


async def _do_r2(session: AsyncSession) -> int:
    """[核销订单过期+改期规则优化 v1.0] 错过预约时段处理。

    PRD 规则（替代旧的"次日全部退回 pending_appointment"逻辑）：
      1) 商品 allow_reschedule=false → 转 expired
      2) 商品 allow_reschedule=true 且 reschedule_count <  reschedule_limit
         → 保持 pending_use，reschedule_count + 1，清空 appointment_time
      3) 商品 allow_reschedule=true 且 reschedule_count >= reschedule_limit
         → 转 expired

    触发条件：status=pending_use 且 任一 OrderItem.appointment_time < 今天 00:00 且 未核销。
    多商品订单：取所有关联商品 allow_reschedule 的「与」（任一禁止改期则按禁止处理）。
    """
    today_start = datetime.combine(datetime.utcnow().date(), dtime(0, 0, 0))
    rows = await session.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items).selectinload(OrderItem.product))
        .where(UnifiedOrder.status == UnifiedOrderStatus.pending_use)
    )
    affected = 0
    now = datetime.utcnow()
    for order in rows.scalars().all():
        appt = _earliest_appt(order)
        if appt is None:
            continue
        if appt >= today_start:
            continue
        any_used = any((it.used_redeem_count or 0) > 0 for it in (order.items or []))
        if any_used:
            continue
        # 计算订单整体是否允许改期
        allow_reschedule = _order_allow_reschedule(order)
        rcount = int(getattr(order, "reschedule_count", 0) or 0)
        rlimit = int(getattr(order, "reschedule_limit", 3) or 3)

        if not allow_reschedule:
            # 规则 1：直接过期
            order.status = UnifiedOrderStatus.expired
            order.updated_at = now
            session.add(Notification(
                user_id=order.user_id,
                title="订单已过期",
                content=f"您的订单 {order.order_no} 已错过预约时段，订单已过期。",
                type=NotificationType.order,
            ))
            affected += 1
            continue

        if rcount < rlimit:
            # 规则 2：保持 pending_use，count+1，清空预约时间
            for it in order.items:
                it.appointment_time = None
            order.reschedule_count = rcount + 1
            order.status = UnifiedOrderStatus.pending_use
            order.updated_at = now
            remaining = rlimit - (rcount + 1)
            session.add(Notification(
                user_id=order.user_id,
                title="预约已重置，请重新预约",
                content=(
                    f"您的订单 {order.order_no} 错过预约时段，已自动重置预约时间，"
                    f"请重新选择。剩余可改期次数：{remaining} 次。"
                ),
                type=NotificationType.order,
            ))
            affected += 1
        else:
            # 规则 3：达上限，转 expired
            order.status = UnifiedOrderStatus.expired
            order.updated_at = now
            session.add(Notification(
                user_id=order.user_id,
                title="订单已过期",
                content=(
                    f"您的订单 {order.order_no} 已达改期上限（{rlimit} 次），"
                    f"订单已过期。"
                ),
                type=NotificationType.order,
            ))
            affected += 1
    if affected:
        logger.info("[R2 reschedule] 处理错过预约订单: %d 笔", affected)
    return affected


def _order_allow_reschedule(order: UnifiedOrder) -> bool:
    """订单整体是否允许改期：任一关联商品禁止 → 整单禁止。"""
    items = order.items or []
    if not items:
        return True
    for it in items:
        prod = getattr(it, "product", None)
        if prod is None:
            continue
        v = getattr(prod, "allow_reschedule", True)
        if v is False:
            return False
    return True


# ──────────────── 提醒推送节点 ────────────────


async def run_appointment_reminders_v2(session: Optional[AsyncSession] = None) -> dict:
    """统一调度提醒节点。每分钟扫描一次，使用窗口 + NotificationLog 去重。

    包含节点：
      - day_before_18 [PRD 订单状态机简化方案 v1.0] T-1 18:00 到店提醒（新）
      - day_before_21：明日 21:00 预约提醒（保留兼容老逻辑）
      - before_30min：临近赴约提醒
      - after_30min：商家在等您
      - after_2h：是否需要改约
      - next_day_9am：未到店重新预约

    Args:
        session: 可选；传入则复用调用方事务（便于测试）；不传则使用生产 async_session。
    """
    counts = {
        "day_before_18": 0,    # T-1 18:00 到店提醒（PRD 主推渠道）
        "day_before_21": 0,
        "before_30min": 0,
        "after_30min": 0,
        "after_2h": 0,
        "next_day_9am": 0,
    }
    own_session = session is None
    session_ctx = async_session() if own_session else _NullCtx(session)
    async with session_ctx as session:  # type: ignore[assignment]
        try:
            # [新增] T-1 18:00 到店提醒：每天 18:00（±5 分钟）扫描所有「明天为预约日」的 pending_use 订单
            counts["day_before_18"] = await _send_window(
                session,
                key="appt_day_before_18",
                title="到店提醒",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=_today_at(0, 0) + timedelta(days=1),  # 明天 00:00
                appt_upper=_today_at(0, 0) + timedelta(days=2),  # 后天 00:00（不含）
                send_window_lower=_today_at(17, 55),
                send_window_upper=_today_at(18, 5),
                content_tpl="您预约的服务明天到期，记得到店核销~ 商家：{store_name}",
            )

            counts["day_before_21"] = await _send_window(
                session,
                key="appt_day_before_21",
                title="明日预约提醒",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=_today_at(0, 0) + timedelta(days=1),
                appt_upper=_today_at(0, 0) + timedelta(days=2),
                send_window_lower=_today_at(20, 55),
                send_window_upper=_today_at(21, 5),
                content_tpl="您明日 {appt} 有 1 笔预约，请准时赴约。",
            )

            counts["before_30min"] = await _send_window(
                session,
                key="appt_before_30min",
                title="临近赴约提醒",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=datetime.utcnow() + timedelta(minutes=25),
                appt_upper=datetime.utcnow() + timedelta(minutes=35),
                send_window_lower=datetime.utcnow() - timedelta(minutes=5),
                send_window_upper=datetime.utcnow() + timedelta(minutes=5),
                content_tpl="您 30 分钟后有预约（{appt}），建议提前出门。",
            )

            counts["after_30min"] = await _send_window(
                session,
                key="appt_after_30min",
                title="商家在等您",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=datetime.utcnow() - timedelta(minutes=35),
                appt_upper=datetime.utcnow() - timedelta(minutes=25),
                send_window_lower=datetime.utcnow() - timedelta(minutes=5),
                send_window_upper=datetime.utcnow() + timedelta(minutes=5),
                content_tpl="您的预约时间 {appt} 已过去 30 分钟，商家在等您，请尽快到店。",
            )

            counts["after_2h"] = await _send_window(
                session,
                key="appt_after_2h",
                title="是否需要改约",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=datetime.utcnow() - timedelta(hours=2, minutes=5),
                appt_upper=datetime.utcnow() - timedelta(hours=1, minutes=55),
                send_window_lower=datetime.utcnow() - timedelta(minutes=5),
                send_window_upper=datetime.utcnow() + timedelta(minutes=5),
                content_tpl="您的预约时间 {appt} 已过去 2 小时仍未到店，是否需要改约？可在订单详情中重新选择时间。",
            )

            counts["next_day_9am"] = await _send_window(
                session,
                key="appt_next_day_9am",
                title="未到店重新预约提醒",
                statuses=[UnifiedOrderStatus.pending_appointment],
                appt_lower=None,
                appt_upper=None,
                send_window_lower=_today_at(8, 55),
                send_window_upper=_today_at(9, 5),
                content_tpl="您有 1 笔订单 {order_no} 未到店，是否重新预约？",
                use_updated_at_window=(
                    _today_at(0, 0) - timedelta(hours=1),
                    _today_at(1, 0),
                ),
            )

            if own_session:
                await session.commit()
        except Exception:
            if own_session:
                await session.rollback()
            logger.exception("appointment reminders v2 failed")
    if any(counts.values()):
        logger.info("[ReminderV2] sent: %s", counts)
    return counts


class _NullCtx:
    """No-op async ctx manager that yields a pre-existing session without closing it."""

    def __init__(self, sess):
        self._sess = sess

    async def __aenter__(self):
        return self._sess

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _send_window(
    session: AsyncSession,
    *,
    key: str,
    title: str,
    statuses: list,
    appt_lower: Optional[datetime],
    appt_upper: Optional[datetime],
    send_window_lower: datetime,
    send_window_upper: datetime,
    content_tpl: str,
    use_updated_at_window: Optional[tuple] = None,
) -> int:
    """发送某节点的提醒，幂等 + 时间窗口控制。

    模板中可用占位符：{appt} / {order_no} / {store_name}

    [PRD 订单状态机简化方案 v1.0] 推送前实时校验：
      - 订单当前状态仍在 statuses 白名单中
      - 订单的预约日期仍在 [appt_lower, appt_upper) 区间内
    （订单从快照查询到推送之间客户可能改预约日 / 取消 / 已核销 → 实时校验拦截）
    """
    now = datetime.utcnow()
    if not (send_window_lower <= now <= send_window_upper):
        return 0

    base_q = select(UnifiedOrder).options(
        selectinload(UnifiedOrder.items),
        selectinload(UnifiedOrder.store),
    )
    base_q = base_q.where(UnifiedOrder.status.in_(statuses))

    if appt_lower is not None and appt_upper is not None:
        sub = (
            select(OrderItem.order_id)
            .where(
                OrderItem.appointment_time.isnot(None),
                OrderItem.appointment_time >= appt_lower,
                OrderItem.appointment_time < appt_upper,
            )
            .distinct()
        )
        base_q = base_q.where(UnifiedOrder.id.in_(sub))

    if use_updated_at_window is not None:
        u_lo, u_hi = use_updated_at_window
        base_q = base_q.where(
            UnifiedOrder.updated_at >= u_lo,
            UnifiedOrder.updated_at <= u_hi,
        )

    rows = await session.execute(base_q)
    sent = 0
    for order in rows.scalars().all():
        # [实时复查] 状态白名单
        cur_status = order.status
        if hasattr(cur_status, "value"):
            cur_status = cur_status.value
        if cur_status not in [s.value if hasattr(s, "value") else s for s in statuses]:
            continue

        # [实时复查] 预约日期窗口
        appt = _earliest_appt(order)
        if appt_lower is not None and appt_upper is not None:
            if appt is None or not (appt_lower <= appt < appt_upper):
                continue

        # 去重：同一订单同一 key 当日只发一次
        today = datetime.utcnow().date()
        dup_q = await session.execute(
            select(NotificationLog).where(
                NotificationLog.user_id == order.user_id,
                NotificationLog.source_type == key,
                NotificationLog.source_id == order.id,
                NotificationLog.created_at >= datetime.combine(today, dtime.min),
            )
        )
        if dup_q.scalar_one_or_none():
            continue

        appt_str = appt.strftime("%Y-%m-%d %H:%M") if appt else "您选定的时间"
        store_name = order.store.store_name if getattr(order, "store", None) else "商家"
        content = content_tpl.format(
            appt=appt_str, order_no=order.order_no, store_name=store_name
        )

        session.add(Notification(
            user_id=order.user_id,
            title=title,
            content=content,
            type=NotificationType.order,
        ))
        session.add(NotificationLog(
            user_id=order.user_id,
            source_type=key,
            source_id=order.id,
            title=title,
            content=content,
            status="sent",
            scheduled_time=now,
        ))
        sent += 1
    return sent


# ──────────────── 懒兜底（接口侧实时翻转） ────────────────


async def lazy_progress_order(order: UnifiedOrder, session: AsyncSession) -> bool:
    """供 unified_orders 接口侧调用：用户/商家打开订单详情时，根据当前时间补翻转。

    [核销订单过期+改期规则优化 v1.0] 应用与 R2 相同的三条规则：
      1) 商品 allow_reschedule=false 错过 → expired
      2) allow_reschedule=true 且 count<limit → 保持 pending_use，count+1，清空预约
      3) allow_reschedule=true 且 count>=limit → expired

    Returns:
        True 表示状态有变化（调用方需 commit）。
    """
    appt = _earliest_appt(order)
    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), dtime(0, 0, 0))

    if appt is not None and order.status == UnifiedOrderStatus.pending_use and appt < today_start:
        any_used = any((it.used_redeem_count or 0) > 0 for it in (order.items or []))
        if not any_used:
            allow = _order_allow_reschedule(order)
            rcount = int(getattr(order, "reschedule_count", 0) or 0)
            rlimit = int(getattr(order, "reschedule_limit", 3) or 3)
            if not allow:
                order.status = UnifiedOrderStatus.expired
                order.updated_at = now
                return True
            if rcount < rlimit:
                for it in order.items:
                    it.appointment_time = None
                order.reschedule_count = rcount + 1
                order.status = UnifiedOrderStatus.pending_use
                order.updated_at = now
                return True
            order.status = UnifiedOrderStatus.expired
            order.updated_at = now
            return True

    # 兼容老订单：appointed 残留 → 直接翻 pending_use
    if order.status == UnifiedOrderStatus.appointed:
        order.status = UnifiedOrderStatus.pending_use
        order.updated_at = now
        return True

    return False


# ──────────────── 数据迁移：appointed → pending_use ────────────────


async def migrate_appointed_to_pending_use(session: AsyncSession) -> int:
    """[PRD 订单状态机简化方案 v1.0 · 第 5.4 节] 一刀切迁移。

    将所有 status='appointed' 的订单刷为 'pending_use'，并写入状态变更日志。
    幂等：重复执行返回 0。
    """
    rows = await session.execute(
        select(UnifiedOrder).where(UnifiedOrder.status == UnifiedOrderStatus.appointed)
    )
    affected = 0
    now = datetime.utcnow()
    for order in rows.scalars().all():
        order.status = UnifiedOrderStatus.pending_use
        order.updated_at = now
        # 写一条用户站内信轨迹（不打扰用户：用 system 类型即可，但保留同一通知通道）
        affected += 1
    if affected:
        logger.info("[Migrate] appointed → pending_use: %d 笔", affected)
    return affected


# ──────────────── 工具函数 ────────────────


def _earliest_appt(order: UnifiedOrder) -> Optional[datetime]:
    times = [it.appointment_time for it in (order.items or []) if it.appointment_time]
    return min(times) if times else None


def _today_at(hour: int, minute: int) -> datetime:
    today = datetime.utcnow().date()
    return datetime.combine(today, dtime(hour, minute))


# ──────────────── 兼容老接口（保留函数名让旧调度配置不报错） ────────────────


async def run_r1_flip_to_pending_use(session: Optional[AsyncSession] = None) -> int:
    """[PRD 订单状态机简化方案 v1.0] R1 已下线（首次预约直接 pending_use）。

    保留函数名以兼容老调度配置；执行时空操作 + 顺手清理任何残留 appointed 订单。
    """
    own_session = session is None
    if own_session:
        session = async_session()  # type: ignore[assignment]
    try:
        if own_session:
            await session.__aenter__()  # type: ignore[union-attr]
        affected = await migrate_appointed_to_pending_use(session)  # type: ignore[arg-type]
        if own_session:
            await session.commit()  # type: ignore[union-attr]
        return affected
    except Exception:
        if own_session:
            await session.rollback()  # type: ignore[union-attr]
        logger.exception("legacy R1 cleanup failed")
        return 0
    finally:
        if own_session:
            try:
                await session.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass
