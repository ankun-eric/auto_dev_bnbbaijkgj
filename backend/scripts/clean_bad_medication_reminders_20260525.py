"""[BUG-HEALTH-PROFILE-MED-20260525 Bug1] 扫描脏数据 MedicationReminder。

历史问题：用药提醒「已结束」Tab 接口 500，根因是部分 status='archived' 的旧记录
在序列化时（`_schedule_from_reminder` / `disease_tags` / `custom_times` 等）抛异常，
导致 `Promise.all` reject → 前端三 Tab 计数全 0、已结束 toast 加载失败。

本脚本仅做 **dry-run 扫描**，不修改任何数据，输出脏数据的 reminder_id 清单，
由运营/开发审核后手工修正。

使用方式（在后端容器内）::

    python -m backend.scripts.clean_bad_medication_reminders_20260525
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clean_bad_med_reminders")


async def _scan() -> None:
    # 延迟导入避免脚本头部依赖 backend.app
    from sqlalchemy import select  # noqa: WPS433

    from app.core.database import async_session  # noqa: WPS433
    from app.models.models import MedicationReminder  # noqa: WPS433

    bad_ids: list[tuple[int, str]] = []
    async with async_session() as db:
        rows = (await db.execute(select(MedicationReminder))).scalars().all()
        for r in rows:
            reasons: list[str] = []
            # 1) custom_times 应为 list[str] 或 None
            ct = r.custom_times
            if ct is not None:
                if isinstance(ct, str):
                    # 尝试 JSON 解析（部分老库可能存的是 JSON 字符串）
                    try:
                        parsed = json.loads(ct)
                        if not isinstance(parsed, list):
                            reasons.append("custom_times_not_list")
                    except Exception:  # noqa: BLE001
                        reasons.append("custom_times_invalid_json")
                elif not isinstance(ct, list):
                    reasons.append(f"custom_times_unexpected_type:{type(ct).__name__}")
            # 2) disease_tags 应为 list 或 None
            dt = r.disease_tags
            if dt is not None and not isinstance(dt, list):
                reasons.append(f"disease_tags_unexpected_type:{type(dt).__name__}")
            # 3) status='archived' 但没有 end_date 也没有 schedule 来源（custom_times / remind_time 都空）
            if (r.status or "") == "archived":
                if not r.custom_times and not r.remind_time and not r.time_period:
                    reasons.append("archived_no_schedule_source")
            if reasons:
                bad_ids.append((r.id, ",".join(reasons)))

    if not bad_ids:
        logger.info("✅ 无脏数据，全部 MedicationReminder 序列化字段均正常")
        return

    logger.warning("⚠️ 发现 %d 条疑似脏数据：", len(bad_ids))
    for rid, reasons in bad_ids:
        logger.warning("  - id=%s  reasons=%s", rid, reasons)
    logger.warning("请运营审核后手工修正（本脚本仅扫描，不修改数据）。")


def main() -> None:
    asyncio.run(_scan())


if __name__ == "__main__":
    main()
