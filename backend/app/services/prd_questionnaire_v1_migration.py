"""[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
通用问卷与图像采集架构数据迁移。

幂等执行：
1. chat_function_buttons 加 3 列：questionnaire_template_id / capture_purpose / pre_card_enabled
2. 旧 pre_card_for_navigate 值回填到新字段 pre_card_enabled
3. 旧 ai_function_type 子类型映射：
   - health_self_check → questionnaire（绑定 health_self_check 模板）
   - report_interpret  → image_capture + capture_purpose=interpret_report
   - photo_upload      → image_capture + capture_purpose=upload
   - medicine_recognize → image_capture + capture_purpose=identify_medicine
4. 预置两个内置问卷模板：health_self_check / tcm_constitution（仅占位，详细题库由运营在后台补全）
"""

import json
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


async def _add_col(db, table: str, column: str, ddl: str) -> None:
    try:
        chk = await db.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
        if (chk.scalar() or 0) == 0:
            await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            print(
                f"[migrate] questionnaire_v1: {table}.{column} 列已添加",
                flush=True,
            )
            logger.info(
                "[questionnaire_v1] %s.%s 列已添加", table, column
            )
    except Exception as e:  # noqa: BLE001
        logger.debug("加列 %s.%s 跳过: %s", table, column, e)


async def _ensure_template(db, code: str, name: str, description: str) -> int | None:
    """确保某编码的问卷模板存在；存在则返回 id，不存在则创建。"""
    try:
        row = await db.execute(
            text("SELECT id FROM questionnaire_template WHERE code = :c"),
            {"c": code},
        )
        rec = row.fetchone()
        if rec:
            return int(rec[0])
        res = await db.execute(
            text(
                "INSERT INTO questionnaire_template "
                "(code, name, description, estimated_minutes, allow_back, "
                " shuffle_questions, report_layout, status, created_at, updated_at) "
                "VALUES (:c, :n, :d, 3, 1, 0, 'standard', 1, NOW(), NOW())"
            ),
            {"c": code, "n": name, "d": description},
        )
        return res.lastrowid
    except Exception as e:  # noqa: BLE001
        logger.debug("[questionnaire_v1] 创建模板 %s 跳过: %s", code, e)
        return None


async def run_migration_with_session(async_session_factory):
    """主迁移入口。

    Args:
        async_session_factory: async_session 工厂函数（如 app.core.database.async_session）

    Returns:
        统计信息 dict
    """
    stats = {
        "columns_added": 0,
        "pre_card_backfilled": 0,
        "questionnaire_mapped": 0,
        "image_capture_mapped": 0,
        "templates_seeded": 0,
    }
    print("[migrate] questionnaire_v1: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            # ── 1. 加 3 列 ──
            await _add_col(
                db,
                "chat_function_buttons",
                "questionnaire_template_id",
                "questionnaire_template_id INT NULL COMMENT '问卷模板 ID（ai_function_type=questionnaire）'",
            )
            await _add_col(
                db,
                "chat_function_buttons",
                "capture_purpose",
                "capture_purpose VARCHAR(32) NULL COMMENT '图像采集用途 identify_medicine/upload/interpret_report'",
            )
            await _add_col(
                db,
                "chat_function_buttons",
                "pre_card_enabled",
                "pre_card_enabled TINYINT(1) NULL DEFAULT 1 COMMENT '是否启用对话内说明卡片（对所有按钮类型统一可用）'",
            )

            # ── 2. pre_card_for_navigate → pre_card_enabled（仅当 pre_card_enabled 为 NULL 时回填）──
            try:
                upd = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET pre_card_enabled = COALESCE(pre_card_for_navigate, 1) "
                        "WHERE pre_card_enabled IS NULL"
                    )
                )
                stats["pre_card_backfilled"] = upd.rowcount or 0
            except Exception as e:  # noqa: BLE001
                logger.debug("pre_card_enabled 回填跳过: %s", e)

            await db.commit()

            # ── 3. 种子模板 ──
            tpl_id_hsc = await _ensure_template(
                db,
                "health_self_check",
                "健康自查",
                "通用症状自查问卷（部位 + 症状 + 持续时间）",
            )
            tpl_id_tcm = await _ensure_template(
                db,
                "tcm_constitution",
                "中医九型体质测评",
                "中医九型体质问卷，60 题判定九种体质",
            )
            if tpl_id_hsc:
                stats["templates_seeded"] += 1
            if tpl_id_tcm:
                stats["templates_seeded"] += 1
            await db.commit()

            # ── 4. 历史按钮子类型映射 ──
            # health_self_check → questionnaire + 绑定 health_self_check 模板
            if tpl_id_hsc:
                try:
                    upd1 = await db.execute(
                        text(
                            "UPDATE chat_function_buttons "
                            "SET ai_function_type = 'questionnaire', "
                            "    questionnaire_template_id = :tid "
                            "WHERE button_type = 'ai_function' "
                            "  AND ai_function_type = 'health_self_check' "
                            "  AND questionnaire_template_id IS NULL"
                        ),
                        {"tid": tpl_id_hsc},
                    )
                    stats["questionnaire_mapped"] += upd1.rowcount or 0
                    # button_type=health_self_check（旧主类型）→ 标记为 ai_function + questionnaire
                    upd1b = await db.execute(
                        text(
                            "UPDATE chat_function_buttons "
                            "SET button_type = 'ai_function', "
                            "    ai_function_type = 'questionnaire', "
                            "    questionnaire_template_id = :tid "
                            "WHERE button_type = 'health_self_check' "
                            "  AND questionnaire_template_id IS NULL"
                        ),
                        {"tid": tpl_id_hsc},
                    )
                    stats["questionnaire_mapped"] += upd1b.rowcount or 0
                except Exception as e:  # noqa: BLE001
                    logger.debug("questionnaire 映射跳过: %s", e)

            # image_capture 三个子用途
            try:
                m = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET ai_function_type = 'image_capture', "
                        "    capture_purpose = 'interpret_report' "
                        "WHERE (ai_function_type = 'report_interpret' "
                        "   OR button_type = 'report_interpret') "
                        "  AND (capture_purpose IS NULL OR capture_purpose = '')"
                    )
                )
                stats["image_capture_mapped"] += m.rowcount or 0
                # 旧 button_type=report_interpret 顺便把主类型也改成 ai_function
                await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET button_type = 'ai_function' "
                        "WHERE button_type = 'report_interpret'"
                    )
                )
                m2 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET ai_function_type = 'image_capture', "
                        "    capture_purpose = 'upload' "
                        "WHERE ai_function_type = 'photo_upload' "
                        "  AND button_type = 'ai_function' "
                        "  AND (capture_purpose IS NULL OR capture_purpose = '')"
                    )
                )
                stats["image_capture_mapped"] += m2.rowcount or 0
                m3 = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET ai_function_type = 'image_capture', "
                        "    capture_purpose = 'identify_medicine' "
                        "WHERE ai_function_type = 'medicine_recognize' "
                        "  AND button_type = 'ai_function' "
                        "  AND (capture_purpose IS NULL OR capture_purpose = '')"
                    )
                )
                stats["image_capture_mapped"] += m3.rowcount or 0
            except Exception as e:  # noqa: BLE001
                logger.debug("image_capture 映射跳过: %s", e)

            await db.commit()
        print(
            f"[migrate] questionnaire_v1: 完成 stats={json.dumps(stats, ensure_ascii=False)}",
            flush=True,
        )
        logger.info("[questionnaire_v1] 完成 stats=%s", stats)
        return stats
    except Exception as e:  # noqa: BLE001
        print(
            f"[migrate] questionnaire_v1: 迁移异常（不影响启动）: {e}",
            flush=True,
        )
        logger.error("[questionnaire_v1] 迁移异常（不影响启动）: %s", e)
        return stats
