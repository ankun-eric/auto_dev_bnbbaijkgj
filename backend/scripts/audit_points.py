"""积分对账脚本（运营人工确认工具）

用途：
    扫描全量用户，对比"由 PointsRecord 流水计算出的可用积分"与 User.points 缓存字段，
    输出差异 CSV 报表到 backend/reports/points_diff_YYYYMMDD.csv。

重要约束（请务必遵守）：
    * 本脚本只读 + 只写 CSV 报表文件；
    * 严禁在本脚本中执行任何 UPDATE/INSERT/DELETE 的数据变更；
    * 差异的修正由运营人工确认后，通过独立流程处理。

用法：
    cd backend && python -m scripts.audit_points

对应 Bug：Bug #4 我的 - 积分 - 积分商城"可用积分"数据 Bug（P0）
口径：可用积分 = 累计获得 − 已消耗 − 已过期 − 已冻结
"""
from __future__ import annotations

import asyncio
import csv
import os
from datetime import datetime

from sqlalchemy import select

# 允许以脚本方式从 backend 目录直接运行
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session  # type: ignore  # noqa: E402
from app.models.models import User  # noqa: E402
from app.api.points import compute_available_points  # noqa: E402


REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


async def audit() -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fname = f"points_diff_{datetime.now().strftime('%Y%m%d')}.csv"
    fpath = os.path.join(REPORTS_DIR, fname)

    async with async_session() as db:
        user_rs = await db.execute(select(User.id, User.phone, User.nickname, User.points))
        rows = user_rs.all()

        diff_rows = []
        for uid, phone, nickname, cached_points in rows:
            breakdown = await compute_available_points(db, uid)
            computed = breakdown["available"]
            cached = int(cached_points or 0)
            if computed != cached:
                diff_rows.append({
                    "user_id": uid,
                    "phone": phone or "",
                    "nickname": nickname or "",
                    "cached_points": cached,
                    "computed_available": computed,
                    "delta": cached - computed,
                    "earned": breakdown["earned"],
                    "consumed": breakdown["consumed"],
                    "expired": breakdown["expired"],
                    "frozen": breakdown["frozen"],
                })

    with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "user_id", "phone", "nickname",
            "cached_points", "computed_available", "delta",
            "earned", "consumed", "expired", "frozen",
        ])
        writer.writeheader()
        for r in diff_rows:
            writer.writerow(r)

    print(f"[audit_points] 扫描完成：共 {len(rows)} 个用户，差异 {len(diff_rows)} 条。")
    print(f"[audit_points] 报表已生成：{fpath}")
    print("[audit_points] 本脚本只生成报表，未做任何数据修正。请运营人工确认后处理。")
    return fpath


if __name__ == "__main__":
    asyncio.run(audit())
