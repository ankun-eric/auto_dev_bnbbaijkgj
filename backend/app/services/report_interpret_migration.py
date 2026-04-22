"""体检报告解读 & 对比相关的默认提示词和模型扩展迁移。

包含：
1. 确保 ``chat_sessions`` 表有 ``report_id`` / ``member_relation`` / ``compare_report_ids`` 字段
2. 确保 ``checkup_reports`` 表有 ``title`` / ``interpret_session_id`` 字段
3. 扩展 SessionType 枚举以包含 ``report_interpret`` / ``report_compare``
4. 往 PromptTemplate 插入默认的两条记录（若尚未存在）

全部操作 **幂等**，启动时由 ``main.py::lifespan`` 调用；异常不阻塞启动。
"""
import logging
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _column_exists(db: AsyncSession, table: str, column: str) -> bool:
    chk = await db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return (chk.scalar() or 0) > 0


async def _add_column_if_missing(db: AsyncSession, table: str, column: str, ddl: str) -> None:
    try:
        if not await _column_exists(db, table, column):
            await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            logger.info("report_interpret_migration: added %s.%s", table, column)
    except Exception as e:  # noqa: BLE001
        logger.debug("report_interpret_migration: add column %s.%s skipped: %s", table, column, e)


async def migrate_report_interpret() -> None:
    """启动时调用：
    1) chat_sessions 新增 report_id / member_relation / compare_report_ids
    2) checkup_reports 新增 title / interpret_session_id
    3) SessionType ENUM 扩容 report_interpret / report_compare
    4) PromptTemplate 默认落两条记录（checkup_report_interpret / checkup_report_compare）
    """
    from app.core.database import async_session as _async_session
    from app.models.models import PromptTemplate
    from app.services.prompts import (
        DEFAULT_REPORT_INTERPRET_PROMPT,
        DEFAULT_REPORT_COMPARE_PROMPT,
    )

    try:
        async with _async_session() as db:
            # --- chat_sessions 字段扩展 ---
            await _add_column_if_missing(
                db, "chat_sessions", "report_id",
                "report_id BIGINT NULL",
            )
            await _add_column_if_missing(
                db, "chat_sessions", "member_relation",
                "member_relation VARCHAR(32) NULL",
            )
            await _add_column_if_missing(
                db, "chat_sessions", "compare_report_ids",
                "compare_report_ids VARCHAR(64) NULL",
            )

            # --- checkup_reports 字段扩展 ---
            await _add_column_if_missing(
                db, "checkup_reports", "title",
                "title VARCHAR(100) NULL",
            )
            await _add_column_if_missing(
                db, "checkup_reports", "interpret_session_id",
                "interpret_session_id BIGINT NULL",
            )

            # --- SessionType ENUM 扩容 ---
            try:
                await db.execute(text(
                    "ALTER TABLE chat_sessions MODIFY COLUMN session_type "
                    "ENUM('health_qa','symptom_check','tcm','tcm_tongue','tcm_face',"
                    "'drug_query','customer_service','drug_identify','constitution_test',"
                    "'report_interpret','report_compare') NOT NULL"
                ))
                logger.info("report_interpret_migration: SessionType ENUM 已扩容")
            except Exception as e:  # noqa: BLE001
                logger.debug("report_interpret_migration: SessionType enum skip: %s", e)

            await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.error("report_interpret_migration DDL 异常（不影响启动）: %s", e)

    # --- 默认 PromptTemplate 落库 ---
    try:
        async with _async_session() as db:
            for ptype, default_content, display_name in [
                ("checkup_report_interpret", DEFAULT_REPORT_INTERPRET_PROMPT, "体检报告解读"),
                ("checkup_report_compare", DEFAULT_REPORT_COMPARE_PROMPT, "报告对比"),
            ]:
                existing = await db.execute(
                    select(PromptTemplate).where(
                        PromptTemplate.prompt_type == ptype,
                        PromptTemplate.is_active.is_(True),
                    )
                )
                if existing.scalar_one_or_none() is None:
                    tpl = PromptTemplate(
                        name=display_name,
                        prompt_type=ptype,
                        content=default_content,
                        version=1,
                        is_active=True,
                    )
                    db.add(tpl)
                    logger.info("report_interpret_migration: inserted default prompt %s", ptype)
            await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.error("report_interpret_migration 默认提示词插入异常: %s", e)
