"""
[PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] AI 咨询配置-功能按钮管理 启动期数据迁移

执行内容（一次性，幂等）：
  1. 把现有 sort_weight 同时复制到 grid_sort / capsule_sort 两个新字段
     （仅当其值为 NULL 或 0 时才覆盖，避免覆盖运营手工设置）
  2. 为老 button_type 行回填 ai_function_type 冗余字段（用于新客户端按子类型派发）：
       photo_upload / file_upload / report_interpret / quick_ask /
       photo_recognize_drug / ai_chat_trigger / health_self_check / ai_dialog_trigger / drug_identify
       → ai_function_type 取对应子类型
     ⚠️ 为兼容已上线的旧客户端，本次迁移**保留 button_type 原值不变**，
        客户端继续按老 button_type 分发；后台保存新按钮时 button_type 写新主类型
        page_navigate / ai_function。这是软性 + 兼容的迁移策略。
  3. 兜底：未识别 button_type 的按钮：ai_function_type=ai_dialog_trigger（不动 button_type）

幂等性：
  通过 app_settings 中 `_migration_done.prd_aichat_funcbtn_optim_v1` 标志，
  已迁移过的不再二次覆盖运营手工设置。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text


_logger = logging.getLogger("app.prd_aichat_funcbtn_optim_v1")


# 老枚举 → ai_function_type 子类型 映射表（兼容策略：button_type 保持不变）
_AI_FUNCTION_TYPE_MAP: Dict[str, str] = {
    "photo_upload": "photo_upload",
    "file_upload": "file_upload",
    "report_interpret": "report_interpret",
    "photo_recognize_drug": "medicine_recognize",
    "drug_identify": "medicine_recognize",
    "ai_chat_trigger": "ai_dialog_trigger",
    "ai_dialog_trigger": "ai_dialog_trigger",
    "quick_ask": "quick_ask",
    "health_self_check": "health_self_check",
}


async def run_migration_with_session(async_session_factory) -> Dict[str, Any]:
    """对外入口：迁移功能按钮表的两个新字段集合（排序值 + 主/子类型）。"""
    stats: Dict[str, Any] = {
        "sort_filled": 0,
        "type_remapped": 0,
        "fallback_count": 0,
        "skipped": False,
    }
    FLAG_KEY = "_migration_done.prd_aichat_funcbtn_optim_v1"

    async with async_session_factory() as db:
        try:
            try:
                res_flag = await db.execute(
                    text("SELECT `value` FROM app_settings WHERE `key` = :k LIMIT 1"),
                    {"k": FLAG_KEY},
                )
                row = res_flag.first()
                if row and row[0]:
                    stats["skipped"] = True
                    return stats
            except Exception:
                # app_settings 不存在或 key 列名不同 → 退化为按 NULL/0 条件迁移
                pass

            # 1. 复制 sort_weight 到 grid_sort / capsule_sort（仅 NULL/0 时覆盖）
            try:
                res_grid = await db.execute(text(
                    "UPDATE chat_function_buttons SET grid_sort = sort_weight "
                    "WHERE (grid_sort IS NULL OR grid_sort = 0) AND sort_weight IS NOT NULL"
                ))
                res_caps = await db.execute(text(
                    "UPDATE chat_function_buttons SET capsule_sort = sort_weight "
                    "WHERE (capsule_sort IS NULL OR capsule_sort = 0) AND sort_weight IS NOT NULL"
                ))
                stats["sort_filled"] = int(getattr(res_grid, "rowcount", 0) or 0) + int(getattr(res_caps, "rowcount", 0) or 0)
            except Exception as exc:
                _logger.exception("[funcbtn-optim-v1] 复制 sort_weight 失败：%s", exc)

            # 2. 为老 button_type 行回填 ai_function_type（不动 button_type，避免破坏老客户端）
            for old_type, ai_fn_type in _AI_FUNCTION_TYPE_MAP.items():
                try:
                    res = await db.execute(
                        text(
                            "UPDATE chat_function_buttons SET "
                            "ai_function_type = :new_ai_fn_type "
                            "WHERE button_type = :old_type AND (ai_function_type IS NULL OR ai_function_type = '')"
                        ),
                        {
                            "new_ai_fn_type": ai_fn_type,
                            "old_type": old_type,
                        },
                    )
                    stats["type_remapped"] += int(getattr(res, "rowcount", 0) or 0)
                except Exception as exc:
                    _logger.exception("[funcbtn-optim-v1] 回填 button_type=%s 的 ai_function_type 失败：%s", old_type, exc)

            # 3. 兜底：未在映射表也未填子类型的按钮（且不是 page_navigate/external_link/digital_human_call 等明显的跳转类）
            try:
                res_fallback = await db.execute(text(
                    "UPDATE chat_function_buttons SET ai_function_type = 'ai_dialog_trigger' "
                    "WHERE (ai_function_type IS NULL OR ai_function_type = '') "
                    "  AND button_type NOT IN ('external_link', 'digital_human_call', 'page_navigate')"
                ))
                stats["fallback_count"] = int(getattr(res_fallback, "rowcount", 0) or 0)
                if stats["fallback_count"] > 0:
                    _logger.warning(
                        "[funcbtn-optim-v1] 兜底归类按钮数 = %s（已归到 ai_function_type=ai_dialog_trigger）",
                        stats["fallback_count"],
                    )
            except Exception as exc:
                _logger.exception("[funcbtn-optim-v1] 兜底归类失败：%s", exc)

            # 4. 写入 app_settings 标志，标记本次迁移已完成
            try:
                await db.execute(
                    text(
                        "INSERT INTO app_settings (`key`, `value`) VALUES (:k, :v) "
                        "ON DUPLICATE KEY UPDATE `value` = :v"
                    ),
                    {"k": FLAG_KEY, "v": "1"},
                )
            except Exception:
                # app_settings 表不存在或字段差异 → 不阻塞
                pass

            await db.commit()
        except Exception as exc:
            await db.rollback()
            _logger.exception("[funcbtn-optim-v1] 迁移出现异常：%s", exc)
            raise

    return stats
