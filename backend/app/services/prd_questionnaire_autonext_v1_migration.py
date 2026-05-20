"""[PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 体质测评自动下一步配置迁移

迁移目标：
1. DDL：chat_function_buttons 表新增三个字段
   - presentation_container VARCHAR(16) DEFAULT 'DRAWER'
   - questions_per_page INT DEFAULT 1
   - auto_next_enabled TINYINT(1) DEFAULT 0
2. 数据：根据旧 questionnaire_display_form 字段回填新字段（存量按钮 auto_next_enabled 保持 0）
   - DRAWER_STEPPED  → (DRAWER, 1, 0)
   - DRAWER_SCROLL   → (DRAWER, 10, 0)
   - INLINE_CHAT     → (INLINE_CHAT, 1, 0)

幂等可重跑：所有 ALTER 与 UPDATE 都先检查后执行。
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


async def _column_exists(db, table: str, column: str) -> bool:
    chk = await db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return (chk.scalar() or 0) > 0


async def _add_col(db, table: str, column: str, ddl: str) -> int:
    try:
        if not await _column_exists(db, table, column):
            await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            print(
                f"[migrate] questionnaire_autonext_v1: {table}.{column} 列已添加",
                flush=True,
            )
            return 1
    except Exception as e:  # noqa: BLE001
        logger.debug("加列 %s.%s 跳过: %s", table, column, e)
    return 0


async def run_migration_with_session(async_session_factory) -> dict:
    stats = {
        "columns_added": 0,
        "container_filled": 0,
        "qpp_filled": 0,
        "auto_next_filled": 0,
    }
    print("[migrate] questionnaire_autonext_v1: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            # 1. DDL ──────────────────────────────────────────────
            stats["columns_added"] += await _add_col(
                db, "chat_function_buttons",
                "presentation_container",
                "presentation_container VARCHAR(16) NULL DEFAULT 'DRAWER' "
                "COMMENT '呈现容器：DRAWER / INLINE_CHAT'",
            )
            stats["columns_added"] += await _add_col(
                db, "chat_function_buttons",
                "questions_per_page",
                "questions_per_page INT NULL DEFAULT 1 "
                "COMMENT '每页题数（1~999），容器=INLINE_CHAT 时无意义'",
            )
            stats["columns_added"] += await _add_col(
                db, "chat_function_buttons",
                "auto_next_enabled",
                "auto_next_enabled TINYINT(1) NULL DEFAULT 0 "
                "COMMENT '是否启用自动下一步（容器=DRAWER 且 每页题数=1 且 问卷全单选 时才可用）'",
            )
            await db.commit()

            # 2. 数据回填 ─────────────────────────────────────────
            # presentation_container：根据老 questionnaire_display_form 映射
            try:
                r1 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET presentation_container = 'INLINE_CHAT' "
                        "WHERE (presentation_container IS NULL OR presentation_container = '') "
                        "  AND questionnaire_display_form = 'INLINE_CHAT'"
                    )
                )
                stats["container_filled"] += r1.rowcount or 0
                r2 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET presentation_container = 'DRAWER' "
                        "WHERE (presentation_container IS NULL OR presentation_container = '') "
                        "  AND (questionnaire_display_form IN ('DRAWER_SCROLL','DRAWER_STEPPED') "
                        "       OR questionnaire_display_form IS NULL)"
                    )
                )
                stats["container_filled"] += r2.rowcount or 0
            except Exception as e:  # noqa: BLE001
                logger.debug("[autonext_v1] presentation_container 回填跳过: %s", e)
            await db.commit()

            # questions_per_page：DRAWER_SCROLL → 10；其它 → 1
            try:
                r3 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET questions_per_page = 10 "
                        "WHERE (questions_per_page IS NULL OR questions_per_page = 0) "
                        "  AND questionnaire_display_form = 'DRAWER_SCROLL'"
                    )
                )
                stats["qpp_filled"] += r3.rowcount or 0
                r4 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET questions_per_page = 1 "
                        "WHERE (questions_per_page IS NULL OR questions_per_page = 0)"
                    )
                )
                stats["qpp_filled"] += r4.rowcount or 0
            except Exception as e:  # noqa: BLE001
                logger.debug("[autonext_v1] questions_per_page 回填跳过: %s", e)
            await db.commit()

            # auto_next_enabled：存量保守保持 0（不影响现有体验）
            try:
                r5 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET auto_next_enabled = 0 "
                        "WHERE auto_next_enabled IS NULL"
                    )
                )
                stats["auto_next_filled"] += r5.rowcount or 0
            except Exception as e:  # noqa: BLE001
                logger.debug("[autonext_v1] auto_next_enabled 回填跳过: %s", e)
            await db.commit()

            # 3. 中医体质测评按钮特殊处理：默认开启自动下一步（36 题全单选）
            try:
                r6 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons cfb "
                        "INNER JOIN questionnaire_template qt "
                        "  ON cfb.questionnaire_template_id = qt.id "
                        "SET cfb.auto_next_enabled = 1, "
                        "    cfb.presentation_container = 'DRAWER', "
                        "    cfb.questions_per_page = 1 "
                        "WHERE qt.code = 'tcm_constitution_wangqi_36' "
                        "  AND cfb.ai_function_type = 'questionnaire' "
                        "  AND cfb.auto_next_enabled = 0"
                    )
                )
                stats["auto_next_filled"] += r6.rowcount or 0
            except Exception as e:  # noqa: BLE001
                logger.debug("[autonext_v1] TCM 按钮自动下一步默认开启跳过: %s", e)
            await db.commit()

        print(
            f"[migrate] questionnaire_autonext_v1: 完成 stats="
            f"{json.dumps(stats, ensure_ascii=False)}",
            flush=True,
        )
        return stats
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] questionnaire_autonext_v1: 异常（不影响启动）: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return stats
