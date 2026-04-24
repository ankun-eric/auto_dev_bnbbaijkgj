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
            # [2026-04-23] 多图修复：新增完整图片 URL 列表字段（JSON）
            await _add_column_if_missing(
                db, "checkup_reports", "file_urls",
                "file_urls JSON NULL",
            )
            await _add_column_if_missing(
                db, "checkup_reports", "thumbnail_urls",
                "thumbnail_urls JSON NULL",
            )

            # --- checkup_report_details 字段扩展（Admin 详情多图）---
            await _add_column_if_missing(
                db, "checkup_report_details", "original_image_urls",
                "original_image_urls JSON NULL",
            )

            # [2026-04-25] 报告解读异步化 - chat_sessions 新增状态字段
            await _add_column_if_missing(
                db, "chat_sessions", "interpret_status",
                "interpret_status VARCHAR(16) DEFAULT 'done'",
            )
            await _add_column_if_missing(
                db, "chat_sessions", "interpret_error",
                "interpret_error TEXT NULL",
            )
            await _add_column_if_missing(
                db, "chat_sessions", "interpret_started_at",
                "interpret_started_at DATETIME NULL",
            )
            await _add_column_if_missing(
                db, "chat_sessions", "interpret_finished_at",
                "interpret_finished_at DATETIME NULL",
            )

            # [2026-04-25] chat_messages 新增 is_hidden 字段
            await _add_column_if_missing(
                db, "chat_messages", "is_hidden",
                "is_hidden TINYINT(1) DEFAULT 0",
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

    # [2026-04-23] 多图回溯：把历史 checkup_reports 的 file_urls 回填为 ocr_call_records.image_urls
    try:
        async with _async_session() as db:
            # 从 ocr_call_records 回填到 checkup_reports：按 ocr_call_record_id 关联 checkup_report_details
            # 并且 checkup_reports 通过 detail.user_id+created_at 附近能定位到的报告
            # 实际采用：CheckupReportDetail.ocr_call_record_id 关联 OcrCallRecord，
            # 再用 detail.user_id + 紧邻 created_at 的 checkup_reports 行做匹配。
            # 这里使用 SQL 直接处理：
            # 1) 用 OcrCallRecord.image_urls 回填 checkup_report_details.original_image_urls
            await db.execute(text(
                """
                UPDATE checkup_report_details d
                JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                SET d.original_image_urls = r.image_urls
                WHERE d.original_image_urls IS NULL
                  AND r.image_urls IS NOT NULL
                """
            ))
            # 2) 对没有关联记录的，fallback 为 [original_image_url]
            await db.execute(text(
                """
                UPDATE checkup_report_details
                SET original_image_urls = JSON_ARRAY(original_image_url)
                WHERE original_image_urls IS NULL AND original_image_url IS NOT NULL
                """
            ))
            # 3) 回填 checkup_reports.file_urls / thumbnail_urls：
            #    用同一个 user_id + 短时间窗口内的 OCR 记录来匹配
            await db.execute(text(
                """
                UPDATE checkup_reports cr
                LEFT JOIN (
                    SELECT d.user_id, r.image_urls,
                           MAX(d.created_at) AS created_at
                    FROM checkup_report_details d
                    JOIN ocr_call_records r ON d.ocr_call_record_id = r.id
                    WHERE r.image_urls IS NOT NULL
                    GROUP BY d.user_id, r.id, r.image_urls
                ) tmp ON tmp.user_id = cr.user_id
                       AND ABS(TIMESTAMPDIFF(SECOND, tmp.created_at, cr.created_at)) < 60
                SET cr.file_urls = tmp.image_urls
                WHERE cr.file_urls IS NULL
                  AND tmp.image_urls IS NOT NULL
                """
            ))
            # 4) 对没有匹配到 OCR 记录的报告：fallback 为 [file_url]
            await db.execute(text(
                """
                UPDATE checkup_reports
                SET file_urls = JSON_ARRAY(file_url)
                WHERE file_urls IS NULL AND file_url IS NOT NULL
                """
            ))
            await db.execute(text(
                """
                UPDATE checkup_reports
                SET thumbnail_urls = JSON_ARRAY(COALESCE(thumbnail_url, file_url))
                WHERE thumbnail_urls IS NULL
                  AND (thumbnail_url IS NOT NULL OR file_url IS NOT NULL)
                """
            ))
            await db.commit()
            logger.info("report_interpret_migration: 多图历史数据回溯完成")
    except Exception as e:  # noqa: BLE001
        logger.error("report_interpret_migration 多图回溯异常（不影响启动）: %s", e)

    # [2026-04-25] 历史数据兼容：把老报告解读/对比会话里显示的"默认用户首问"标记为隐藏
    try:
        async with _async_session() as db:
            await db.execute(text(
                """
                UPDATE chat_messages
                SET is_hidden = 1
                WHERE role = 'user'
                  AND (
                    content LIKE '%请帮我解读这份报告%'
                    OR content LIKE '%请帮我对比这两份报告%'
                    OR content LIKE '%请帮我解读%'
                    OR content LIKE '%咨询对象：%'
                  )
                  AND session_id IN (
                    SELECT id FROM chat_sessions WHERE session_type IN ('report_interpret','report_compare')
                  )
                """
            ))
            await db.commit()
            logger.info("report_interpret_migration: 历史隐藏首问迁移完成")
    except Exception as e:  # noqa: BLE001
        logger.error("report_interpret_migration 历史隐藏首问迁移异常（不影响启动）: %s", e)
