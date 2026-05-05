"""[PRD-01 全平台固定时段切片体系 v1.0 · F-01-7] 历史订单 time_slot 一次性回填脚本

背景
----
PRD-01 把全平台预约时段统一为固定 9 段（每段 2 小时，最早 06:00），并在
`unified_orders` 表新增 `time_slot` (INT NULL, 段号 1-9) 字段。下单 / 改期路径
已经在新代码里自动写入；但历史订单 `time_slot` 字段都是 NULL，需要本脚本
一次性回填。

回填规则（与 PRD R-01 完全对齐）
----------------------------------
- 取订单下「首个有 appointment_time 的 OrderItem」的 appointment_time
- 按起始 hour 归段（appointment_to_slot）：
    · hour < 6 (凌晨段)               → time_slot = NULL（PRD R-01-04 列表可见、9 宫格不渲染）
    · 6 ≤ hour < 8                    → time_slot = 1
    · 8 ≤ hour < 10                   → 2
    · 10 ≤ hour < 12                  → 3
    · 12 ≤ hour < 14                  → 4
    · 14 ≤ hour < 16                  → 5
    · 16 ≤ hour < 18                  → 6
    · 18 ≤ hour < 20                  → 7
    · 20 ≤ hour < 22                  → 8
    · hour ≥ 22                       → 9（含跨日 22:00-次日 00:00）
- 整单无 appointment_time（先下单后预约 / 实物商品）  → time_slot = NULL

幂等
----
- 仅扫 `time_slot IS NULL` 的订单
- 反复执行不会改写已有非 NULL 的字段
- 凌晨段订单仍保持 NULL，下次执行时仍会被跳过（不会反复落地为同一值）

用法
----
    cd backend && python -m scripts.backfill_unified_orders_time_slot            # dry-run（默认）
    cd backend && python -m scripts.backfill_unified_orders_time_slot --apply    # 真实写库

输出会打印：扫描总数 / 待回填总数 / 各段命中分布 / 凌晨段保留 NULL 数。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session  # type: ignore  # noqa: E402
from app.models.models import UnifiedOrder  # noqa: E402
from app.utils.time_slots import appointment_to_slot  # noqa: E402


async def _scan_and_backfill(apply_changes: bool) -> dict:
    counters = Counter()
    counters["scanned"] = 0
    counters["filled_nonnull"] = 0
    counters["kept_null_overnight"] = 0
    counters["kept_null_no_appt"] = 0

    slot_distribution = Counter()

    async with async_session() as session:
        stmt = (
            select(UnifiedOrder)
            .options(selectinload(UnifiedOrder.items))
            .where(UnifiedOrder.time_slot.is_(None))
        )
        rows = (await session.execute(stmt)).scalars().all()
        counters["scanned"] = len(rows)

        for order in rows:
            first_appt_time = None
            for it in (order.items or []):
                appt = getattr(it, "appointment_time", None)
                if appt:
                    first_appt_time = appt
                    break

            if first_appt_time is None:
                counters["kept_null_no_appt"] += 1
                continue

            slot_no = appointment_to_slot(first_appt_time)
            if slot_no is None:
                counters["kept_null_overnight"] += 1
                print(
                    f"  [skip overnight] order_id={order.id} "
                    f"order_no={order.order_no} appt={first_appt_time.isoformat()}"
                )
                continue

            slot_distribution[slot_no] += 1
            counters["filled_nonnull"] += 1
            print(
                f"  [fill] order_id={order.id} order_no={order.order_no} "
                f"appt={first_appt_time.isoformat()} -> slot={slot_no}"
            )

            if apply_changes:
                order.time_slot = slot_no

        if apply_changes:
            await session.commit()
        else:
            await session.rollback()

    return {"counters": counters, "slot_distribution": slot_distribution}


def _print_report(report: dict, apply_changes: bool) -> None:
    counters = report["counters"]
    dist = report["slot_distribution"]
    mode = "APPLY" if apply_changes else "DRY-RUN"
    print("\n" + "=" * 60)
    print(f"[backfill_unified_orders_time_slot] {mode} 结果")
    print("=" * 60)
    print(f"扫描 unified_orders.time_slot IS NULL 总数 : {counters['scanned']}")
    print(f"待/已回填段号 1-9 订单数               : {counters['filled_nonnull']}")
    print(f"凌晨段（保留 NULL）订单数              : {counters['kept_null_overnight']}")
    print(f"无 appointment_time（保留 NULL）订单数  : {counters['kept_null_no_appt']}")
    if dist:
        print("各段命中分布:")
        for slot_no in sorted(dist):
            print(f"  - 段 {slot_no}: {dist[slot_no]} 单")
    if not apply_changes:
        print("\n[!] 当前为 dry-run 模式，未修改任何数据。加 --apply 才会真实写库。")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="[PRD-01 F-01-7] 历史订单 unified_orders.time_slot 一次性回填",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真实写库（默认 dry-run，仅打印）",
    )
    args = parser.parse_args()

    report = asyncio.run(_scan_and_backfill(args.apply))
    _print_report(report, args.apply)


if __name__ == "__main__":
    main()
