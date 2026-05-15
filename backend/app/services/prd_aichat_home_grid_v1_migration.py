"""
[PRD-AICHAT-HOME-GRID-V1 2026-05-16] AI 对话首页（ai-home）功能宫格与胶囊条优化 启动期数据迁移

执行内容：
  1. 历史 chat_function_buttons 表中 is_enabled = true 的按钮：
       is_recommended = true, is_capsule = true（两个开关都 ON）
  2. 历史 is_enabled = false 的按钮：
       is_recommended = false, is_capsule = false

幂等性：
  本脚本只对 is_recommended / is_capsule 仍为 NULL 的行执行写入，
  已设置过两个新开关（无论 True/False）的行不再覆盖，重复执行安全。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text


_logger = logging.getLogger("app.prd_aichat_home_grid_v1")


async def run_migration_with_session(async_session_factory) -> Dict[str, Any]:
    """对外入口：根据 is_enabled 历史值，回填 is_recommended / is_capsule。仅对 NULL 列回填。"""
    stats: Dict[str, Any] = {"migrated_enabled": 0, "migrated_disabled": 0}
    async with async_session_factory() as db:
        try:
            # 仅迁移两列均为 NULL 的历史行（防覆盖已被运营人工设置过的值）
            res_enabled = await db.execute(text(
                "UPDATE chat_function_buttons "
                "SET is_recommended = 1, is_capsule = 1 "
                "WHERE (is_recommended IS NULL AND is_capsule IS NULL) "
                "  AND is_enabled = 1"
            ))
            stats["migrated_enabled"] = int(getattr(res_enabled, "rowcount", 0) or 0)
            res_disabled = await db.execute(text(
                "UPDATE chat_function_buttons "
                "SET is_recommended = 0, is_capsule = 0 "
                "WHERE (is_recommended IS NULL AND is_capsule IS NULL) "
                "  AND (is_enabled = 0 OR is_enabled IS NULL)"
            ))
            stats["migrated_disabled"] = int(getattr(res_disabled, "rowcount", 0) or 0)
            await db.commit()
        except Exception as e:
            await db.rollback()
            _logger.warning("[PRD-AICHAT-HOME-GRID-V1] 迁移失败：%s", e)
            stats["error"] = str(e)
    _logger.info("[PRD-AICHAT-HOME-GRID-V1] 迁移完成：%s", stats)
    return stats
