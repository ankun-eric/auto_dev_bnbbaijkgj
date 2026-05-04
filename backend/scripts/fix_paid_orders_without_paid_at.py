"""[H5 支付链路修复 v1.0] 历史数据校准脚本

背景：
    早期版本中，存在订单状态已推进到"已结算"区间（pending_shipment/pending_use
    /completed/...）但 `paid_at` 仍为 NULL 的脏数据。本脚本扫描全表，把这些
    订单回退到 `pending_payment`，让用户可重新走支付链路或人工处理。

只回退**有应付金额（paid_amount > 0）**且 `paid_at IS NULL` 的订单；0 元订单
另由 confirm-free 链路负责，已通过新接口产生的 0 元订单不会落入此范围。

约束：
    * `--dry-run`（默认）只读 + 打印；
    * `--apply` 才执行 UPDATE，修改 status / updated_at；
    * 每条修改前后 status 都会打印；
    * 不会触碰 paid_amount、paid_at、payment_channel_code 等其它字段。

用法：
    cd backend && python -m scripts.fix_paid_orders_without_paid_at            # dry-run
    cd backend && python -m scripts.fix_paid_orders_without_paid_at --apply    # 真实写库
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session  # type: ignore  # noqa: E402
from app.models.models import UnifiedOrder, UnifiedOrderStatus  # noqa: E402


SETTLED_STATUSES = [
    UnifiedOrderStatus.pending_shipment,
    UnifiedOrderStatus.pending_receipt,
    UnifiedOrderStatus.pending_use,
    UnifiedOrderStatus.pending_review,
    UnifiedOrderStatus.completed,
    UnifiedOrderStatus.partial_used,
    UnifiedOrderStatus.appointed,
    UnifiedOrderStatus.pending_appointment,
]


def _status_str(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


async def run(apply_changes: bool) -> int:
    async with async_session() as db:
        stmt = select(UnifiedOrder).where(
            UnifiedOrder.status.in_(SETTLED_STATUSES),
            UnifiedOrder.paid_at.is_(None),
            UnifiedOrder.paid_amount > 0,
        )
        rs = await db.execute(stmt)
        orders = rs.scalars().all()

        print(f"[fix_paid_orders] 命中订单数: {len(orders)}")
        print("-" * 80)
        print(f"{'order_no':<24} {'status':<22} {'paid_amount':>12} {'created_at'}")
        print("-" * 80)
        for o in orders:
            print(
                f"{o.order_no:<24} {_status_str(o.status):<22} "
                f"{float(o.paid_amount or 0):>12.2f} {o.created_at}"
            )

        if not apply_changes:
            print("-" * 80)
            print("[fix_paid_orders] dry-run 模式，未修改任何数据。如需写库请加 --apply。")
            return len(orders)

        # --apply
        print("-" * 80)
        print("[fix_paid_orders] 开始执行修复（status -> pending_payment）...")
        for o in orders:
            old_status = _status_str(o.status)
            o.status = UnifiedOrderStatus.pending_payment
            o.updated_at = datetime.utcnow()
            print(
                f"  [UPDATE] order_no={o.order_no} status: "
                f"{old_status} -> {_status_str(o.status)}"
            )
        await db.commit()
        print(f"[fix_paid_orders] 修复完成，共 {len(orders)} 条已写库。")
        return len(orders)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="校准 paid_at IS NULL 的已结算订单")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="（默认）只打印不修改")
    g.add_argument("--apply", action="store_true", default=False,
                   help="实际写入数据库（status -> pending_payment）")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run(apply_changes=bool(args.apply)))
