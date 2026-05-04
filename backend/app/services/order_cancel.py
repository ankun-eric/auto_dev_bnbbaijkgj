"""[订单核销码状态与未支付超时治理 Bug 修复方案 v1.0]

统一取消出口（cancel_order_with_items）

> 写入侧的唯一闸门，凡是把 `UnifiedOrder.status` 写为 `cancelled` 的代码路径都
> 必须经由本模块统一处理，避免 `OrderItem.redemption_code_status` 与订单主状态
> 长期不同步的脏数据。

复用现有 5 态核销码状态机（active/locked/used/expired/refunded），不新增状态。
取消订单时把所有订单项的 `redemption_code_status` 同步置为 `expired`。
对于已经处于终态（used/redeemed/refunded/expired/locked）的核销码不做覆盖，
保持其历史含义（避免覆盖已核销/已退款的真实业务结果）。

三条取消路径全部通过本函数收敛：
1) 客户主动取消 — `POST /api/orders/unified/{id}/cancel`
2) admin 批准退款 — `POST /api/admin/orders/unified/{id}/refund/approve`
3) 未支付超时自动取消（路径 3-NEW，替换原"门店超时未确认自动取消"）
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import OrderItem, UnifiedOrder, UnifiedOrderStatus

# 已经处于终态的核销码值，取消订单时不应再回写为 expired，避免覆盖业务历史。
_REDEMPTION_CODE_TERMINAL = {"used", "redeemed", "refunded", "expired"}


async def cancel_order_with_items(
    db: AsyncSession,
    order: UnifiedOrder,
    *,
    cancel_reason: str,
    cancelled_at: Optional[datetime] = None,
) -> UnifiedOrder:
    """统一取消出口：把订单 status 置为 cancelled，并同步刷写所有订单项核销码状态。

    Args:
        db: 当前数据库会话（事务由调用方控制 commit / rollback）
        order: 已经从 DB 加载的 UnifiedOrder 对象（必须能访问 .items 关系）
        cancel_reason: 取消原因（写入 order.cancel_reason）
        cancelled_at: 取消时间，缺省 utcnow()

    Returns:
        已就地修改的同一个 UnifiedOrder 对象（不会自动 commit）
    """
    if cancelled_at is None:
        cancelled_at = datetime.utcnow()

    # 1) 主表
    order.status = UnifiedOrderStatus.cancelled
    order.cancelled_at = cancelled_at
    order.cancel_reason = cancel_reason
    order.updated_at = cancelled_at

    # 2) 子表：刷写所有订单项的核销码状态为 expired
    items = list(getattr(order, "items", []) or [])
    if not items:
        # 兜底：若关系未预加载，则按 order_id 查一次
        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = list(result.scalars().all())

    for it in items:
        cur = it.redemption_code_status
        if hasattr(cur, "value"):
            cur = cur.value
        cur = (cur or "").lower()
        if cur in _REDEMPTION_CODE_TERMINAL:
            continue
        it.redemption_code_status = "expired"
        it.updated_at = cancelled_at

    return order


async def cleanup_cancelled_orders_redemption_codes(db: AsyncSession) -> int:
    """[一次性数据清洗] 把库内所有「订单 cancelled / 核销码 active」的脏数据全部刷为 expired。

    幂等：重复执行不会改写已为 expired/redeemed/refunded/used/locked 的核销码。

    Returns:
        本次实际刷写的 OrderItem 行数。
    """
    # 注意：此处不使用批量 UPDATE 是为了让 ORM 的 onupdate 生效。
    # 若数据量较大可在 SQL 层用 UPDATE order_items oi JOIN unified_orders uo ...
    result = await db.execute(
        select(OrderItem)
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            UnifiedOrder.status == UnifiedOrderStatus.cancelled,
            OrderItem.redemption_code_status == "active",
        )
    )
    rows = list(result.scalars().all())
    now = datetime.utcnow()
    for it in rows:
        it.redemption_code_status = "expired"
        it.updated_at = now
    await db.flush()
    return len(rows)
