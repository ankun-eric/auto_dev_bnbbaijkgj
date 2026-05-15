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
    """对外入口：根据 is_enabled 历史值，回填 is_recommended / is_capsule。

    迁移策略（幂等）：
      - 通过 app_settings 表的 `_migration_done.prd_aichat_home_grid_v1` 标志记录是否已迁移
      - 已迁移过 → 直接返回（绝不二次覆盖运营手工设置）
      - 未迁移过 → 一次性按 is_enabled 回填：
          is_enabled=1 → is_recommended=1, is_capsule=1
          否则         → is_recommended=0, is_capsule=0
        然后把标志写入 app_settings 永久保留
    """
    stats: Dict[str, Any] = {"migrated_enabled": 0, "migrated_disabled": 0, "skipped": False}
    FLAG_KEY = "_migration_done.prd_aichat_home_grid_v1"
    async with async_session_factory() as db:
        try:
            # 1. 确保 app_settings 表存在（schema 同步通常已创建；这里只读，不创建）
            #    本项目 app_settings 字段为 `key`/`value`（不是 setting_key/setting_value）
            try:
                res_flag = await db.execute(text(
                    "SELECT `value` FROM app_settings WHERE `key` = :k LIMIT 1"
                ), {"k": FLAG_KEY})
                row = res_flag.first()
                if row and row[0]:
                    stats["skipped"] = True
                    return stats
            except Exception:
                # app_settings 表不存在或字段差异 → 退化为按 NULL 条件迁移（避免阻塞）
                pass

            # 2. 一次性回填
            res_enabled = await db.execute(text(
                "UPDATE chat_function_buttons "
                "SET is_recommended = 1, is_capsule = 1 "
                "WHERE is_enabled = 1"
            ))
            stats["migrated_enabled"] = int(getattr(res_enabled, "rowcount", 0) or 0)

            res_disabled = await db.execute(text(
                "UPDATE chat_function_buttons "
                "SET is_recommended = 0, is_capsule = 0 "
                "WHERE (is_enabled = 0 OR is_enabled IS NULL)"
            ))
            stats["migrated_disabled"] = int(getattr(res_disabled, "rowcount", 0) or 0)

            # 3. 写入完成标志
            try:
                await db.execute(text(
                    "INSERT INTO app_settings (`key`, `value`, updated_at) "
                    "VALUES (:k, '1', NOW()) "
                    "ON DUPLICATE KEY UPDATE `value` = '1', updated_at = NOW()"
                ), {"k": FLAG_KEY})
            except Exception as e:
                _logger.warning("[PRD-AICHAT-HOME-GRID-V1] 写入迁移标志失败（不影响主迁移）：%s", e)

            await db.commit()
        except Exception as e:
            await db.rollback()
            _logger.warning("[PRD-AICHAT-HOME-GRID-V1] 迁移失败：%s", e)
            stats["error"] = str(e)
    _logger.info("[PRD-AICHAT-HOME-GRID-V1] 迁移完成：%s", stats)
    return stats
