"""[PRD-HSC-OPTIM-V3-20260521] 健康自查功能优化 V3 迁移脚本

新增字段：
1. questionnaire_answer 表（注意：实际表名是 questionnaire_answer 单数）
   - subject_kind        VARCHAR(16)  NULL  本人/家人
   - subject_member_id   INT          NULL  家人ID
   - subject_name        VARCHAR(64)  NULL  被测人姓名
   - subject_relation    VARCHAR(32)  NULL  亲属关系
   - ai_status           VARCHAR(16)  NULL  pending/done/failed (默认 done 对旧数据)
   - ai_failed_reason    VARCHAR(255) NULL
   - ai_full_interpretation TEXT      NULL  异步生成的解读
   - home_care_tips      JSON         NULL
   - red_flag_signals    JSON         NULL
   - archive_insufficient TINYINT(1)  NULL  档案不足标志

2. chat_function_buttons 表
   - result_cta_enabled       TINYINT(1)   NULL  是否在结果详情页显示 CTA
   - result_cta_text          VARCHAR(32)  NULL  按钮文案
   - result_cta_target_type   VARCHAR(16)  NULL  跳转类型
   - result_cta_target_value  VARCHAR(255) NULL  跳转值

设计原则（极度保守）：
- 幂等：可重复执行；通过 INFORMATION_SCHEMA 检查列是否已存在
- 历史数据：ai_status 默认填 'done'（认为已是终态，不触发轮询）
- 不影响主启动流程：任何步骤失败仅记录日志、不抛错

执行入口：`run_migration_with_session(db)` —— 在 main.py 的 lifespan 调用。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)

_SENTINEL_PHASE = "hsc_optim_v3"


async def _ensure_phase_state_table(db: AsyncSession) -> None:
    try:
        await db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS prd_phase_state (
                  phase VARCHAR(64) PRIMARY KEY,
                  status VARCHAR(32) NOT NULL,
                  detail TEXT NULL,
                  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP
                ) DEFAULT CHARSET=utf8mb4;
                """
            )
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_optim_v3] create prd_phase_state failed: %s", e)


async def _get_phase_status(db: AsyncSession) -> Optional[str]:
    try:
        row = (
            await db.execute(
                text("SELECT status FROM prd_phase_state WHERE phase = :p"),
                {"p": _SENTINEL_PHASE},
            )
        ).first()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


async def _set_phase_status(db: AsyncSession, status: str, detail: str = "") -> None:
    try:
        await db.execute(
            text(
                """
                INSERT INTO prd_phase_state (phase, status, detail)
                VALUES (:p, :s, :d)
                ON DUPLICATE KEY UPDATE status = :s, detail = :d
                """
            ),
            {"p": _SENTINEL_PHASE, "s": status, "d": detail[:1000]},
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_optim_v3] set phase status failed: %s", e)


async def _column_exists(db: AsyncSession, table: str, column: str) -> bool:
    try:
        row = (
            await db.execute(
                text(
                    """
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :t AND COLUMN_NAME = :c
                    LIMIT 1
                    """
                ),
                {"t": table, "c": column},
            )
        ).first()
        return bool(row)
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_optim_v3] _column_exists(%s.%s) failed: %s", table, column, e)
        return False


async def _add_column_safe(db: AsyncSession, table: str, column: str, ddl: str) -> bool:
    """安全添加列：列已存在则跳过；失败仅记录日志不抛错。返回是否新增。"""
    if await _column_exists(db, table, column):
        return False
    try:
        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        await db.commit()
        _logger.info("[hsc_optim_v3] +column %s.%s", table, column)
        return True
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_optim_v3] ADD COLUMN %s.%s failed: %s", table, column, e)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


async def run_migration_with_session(db: AsyncSession) -> dict:
    """主入口：在 main.py 的 lifespan 调用。"""
    stats = {"answer_added": 0, "button_added": 0, "backfilled": 0}
    try:
        await _ensure_phase_state_table(db)
        existing = await _get_phase_status(db)
        # 1. questionnaire_answer 新增字段
        ans_table = "questionnaire_answer"
        ans_cols = [
            ("subject_kind", "VARCHAR(16) NULL COMMENT '本人/家人 self/family'"),
            ("subject_member_id", "INT NULL COMMENT '家人 ID'"),
            ("subject_name", "VARCHAR(64) NULL COMMENT '被测人姓名'"),
            ("subject_relation", "VARCHAR(32) NULL COMMENT '亲属关系'"),
            ("ai_status", "VARCHAR(16) NULL DEFAULT 'done' COMMENT 'pending/done/failed'"),
            ("ai_failed_reason", "VARCHAR(255) NULL COMMENT 'AI 解读失败原因'"),
            ("ai_full_interpretation", "TEXT NULL COMMENT '异步生成的解读'"),
            ("home_care_tips_json", "JSON NULL COMMENT '居家建议'"),
            ("red_flag_signals_json", "JSON NULL COMMENT '红线信号'"),
            ("archive_insufficient", "TINYINT(1) NULL DEFAULT 0 COMMENT '档案不足标志'"),
        ]
        for col, ddl in ans_cols:
            if await _add_column_safe(db, ans_table, col, ddl):
                stats["answer_added"] += 1

        # 历史数据兜底：将 ai_status 为 NULL 的记录置 'done'
        try:
            res = await db.execute(
                text(f"UPDATE {ans_table} SET ai_status='done' WHERE ai_status IS NULL")
            )
            await db.commit()
            stats["backfilled"] = int(getattr(res, "rowcount", 0) or 0)
        except Exception as e:  # noqa: BLE001
            _logger.warning("[hsc_optim_v3] backfill ai_status failed: %s", e)
            try:
                await db.rollback()
            except Exception:
                pass

        # 2. chat_function_buttons 新增字段
        btn_table = "chat_function_buttons"
        btn_cols = [
            ("result_cta_enabled", "TINYINT(1) NULL DEFAULT 0 COMMENT '是否在结果详情页显示 CTA'"),
            ("result_cta_text", "VARCHAR(32) NULL COMMENT '按钮文案'"),
            ("result_cta_target_type", "VARCHAR(16) NULL COMMENT 'H5_PATH/EXTERNAL_URL/MINIPROGRAM_PATH/DOCTOR_ID/DEPARTMENT_ID'"),
            ("result_cta_target_value", "VARCHAR(255) NULL COMMENT '跳转目标值'"),
        ]
        for col, ddl in btn_cols:
            if await _add_column_safe(db, btn_table, col, ddl):
                stats["button_added"] += 1

        await _set_phase_status(db, "done", str(stats))
        _logger.info("[migrate] hsc_optim_v3: 迁移完成 stats=%s", stats)
    except Exception as e:  # noqa: BLE001
        _logger.exception("[migrate] hsc_optim_v3 failed: %s", e)
    return stats
