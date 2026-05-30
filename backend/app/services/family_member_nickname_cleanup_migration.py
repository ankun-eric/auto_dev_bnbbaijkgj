"""[BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530] 健康档案空姓名脏数据清理 + 列约束加固

修复目标：
1. 清理 `family_members` 表中 `nickname IS NULL` 或 `TRIM(nickname)=''` 的脏档案
   - 仅清理 `is_self=0` 的非本人档（确认零误删本人档风险）
   - 级联清理下挂数据，按真实 schema 处理：
     * health_profiles (family_member_id) —— 先删其子表 health_info_extra / health_events / medical_record_cards
     * family_invitations (member_id)
     * family_management (managed_member_id)
     * 其余引用 family_members(id) 的表：
       chat_sessions(family_member_id), checkup_reports(family_member_id),
       device_user_bindings(member_id), drug_identify_details(family_member_id),
       health_alert_notifications(member_id), health_reminders(member_id),
       report_history(family_member_id), tcm_diagnoses(family_member_id)
2. 把列改为 NOT NULL（`ALTER TABLE family_members MODIFY nickname VARCHAR(100) NOT NULL`）

幂等性：每步均可重复执行；ALTER 已 NOT NULL 时再次执行 MySQL 等同 no-op。
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import async_session

logger = logging.getLogger(__name__)


# 按真实 schema 整理的级联删除清单
# 直接挂在 family_members(id) 的子表
_DIRECT_CHILD_TABLES: list[tuple[str, str]] = [
    # (表名, 引用 family_members.id 的列名)
    ("family_invitations", "member_id"),
    ("family_management", "managed_member_id"),
    ("chat_sessions", "family_member_id"),
    ("checkup_reports", "family_member_id"),
    ("device_user_bindings", "member_id"),
    ("drug_identify_details", "family_member_id"),
    ("health_alert_notifications", "member_id"),
    ("health_reminders", "member_id"),
    ("report_history", "family_member_id"),
    ("tcm_diagnoses", "family_member_id"),
]

# 挂在 health_profiles(id) 的孙表，必须先删
_HEALTH_PROFILE_GRANDCHILDREN: list[tuple[str, str]] = [
    ("health_info_extra", "profile_id"),
    ("health_events", "profile_id"),
    ("medical_record_cards", "profile_id"),
]

# 挂在 family_management(id) 的孙表，必须在删 family_management 前先删
_FAMILY_MANAGEMENT_GRANDCHILDREN: list[tuple[str, str]] = [
    ("management_operation_logs", "management_id"),
]


async def _safe_exec(db, sql: str, label: str) -> int:
    """执行 DELETE，返回影响行数；失败仅 WARNING 不抛。"""
    try:
        result = await db.execute(text(sql))
        affected = result.rowcount if hasattr(result, "rowcount") else -1
        if affected and affected > 0:
            logger.info(
                "[migrate] family_member_nickname_cleanup: %s 删除 %d 行",
                label,
                affected,
            )
        return affected if affected and affected > 0 else 0
    except Exception as e:
        # 1146=表不存在; 1054=列不存在; 1451=外键约束。任何错误都不阻断整体
        logger.warning(
            "[migrate] family_member_nickname_cleanup: %s 失败 err=%s",
            label,
            e,
        )
        return 0


async def migrate_family_member_nickname_cleanup() -> None:
    """清理姓名为空脏档案 + 把 nickname 列加 NOT NULL 约束。"""
    try:
        async with async_session() as db:
            # 1) 列出待清理主档 ID（仅非本人档）
            dirty_rows = (
                await db.execute(
                    text(
                        """
                        SELECT id FROM family_members
                        WHERE (nickname IS NULL OR TRIM(nickname) = '')
                          AND (is_self = 0 OR is_self IS NULL)
                        """
                    )
                )
            ).fetchall()
            dirty_ids = [int(r[0]) for r in dirty_rows]

            if dirty_ids:
                logger.warning(
                    "[migrate] family_member_nickname_cleanup: 发现 %d 条空姓名脏档案 ids=%s",
                    len(dirty_ids),
                    dirty_ids[:50],
                )

                id_list_sql = ",".join(str(i) for i in dirty_ids)

                # 2-a) 先取 health_profiles 的 id（这些 profile 即将被删，其孙表先删）
                try:
                    hp_rows = (
                        await db.execute(
                            text(
                                f"SELECT id FROM health_profiles "
                                f"WHERE family_member_id IN ({id_list_sql})"
                            )
                        )
                    ).fetchall()
                    hp_ids = [int(r[0]) for r in hp_rows]
                except Exception as e:
                    logger.warning(
                        "[migrate] family_member_nickname_cleanup: 查 health_profiles ids 失败 err=%s",
                        e,
                    )
                    hp_ids = []

                if hp_ids:
                    hp_id_sql = ",".join(str(i) for i in hp_ids)
                    # 2-b) 先删 health_profiles 的孙表
                    for tbl, col in _HEALTH_PROFILE_GRANDCHILDREN:
                        await _safe_exec(
                            db,
                            f"DELETE FROM {tbl} WHERE {col} IN ({hp_id_sql})",
                            f"{tbl}",
                        )

                # 2-c) 删 health_profiles（直接挂在 family_members）
                await _safe_exec(
                    db,
                    f"DELETE FROM health_profiles WHERE family_member_id IN ({id_list_sql})",
                    "health_profiles",
                )

                # 2-d-pre) 先取 family_management.id（这些 fm 即将被删，其孙表 management_operation_logs 先删）
                try:
                    mg_rows = (
                        await db.execute(
                            text(
                                f"SELECT id FROM family_management "
                                f"WHERE managed_member_id IN ({id_list_sql})"
                            )
                        )
                    ).fetchall()
                    mg_ids = [int(r[0]) for r in mg_rows]
                except Exception as e:
                    logger.warning(
                        "[migrate] family_member_nickname_cleanup: 查 family_management ids 失败 err=%s",
                        e,
                    )
                    mg_ids = []
                if mg_ids:
                    mg_id_sql = ",".join(str(i) for i in mg_ids)
                    for tbl, col in _FAMILY_MANAGEMENT_GRANDCHILDREN:
                        await _safe_exec(
                            db,
                            f"DELETE FROM {tbl} WHERE {col} IN ({mg_id_sql})",
                            f"{tbl}",
                        )

                # 2-d) 删其余直接子表
                for tbl, col in _DIRECT_CHILD_TABLES:
                    await _safe_exec(
                        db,
                        f"DELETE FROM {tbl} WHERE {col} IN ({id_list_sql})",
                        tbl,
                    )

                # 3) 删主档
                await _safe_exec(
                    db,
                    f"""
                    DELETE FROM family_members
                    WHERE id IN ({id_list_sql})
                      AND (is_self = 0 OR is_self IS NULL)
                    """,
                    "family_members 主档",
                )

                try:
                    await db.commit()
                except Exception as e:
                    logger.warning(
                        "[migrate] family_member_nickname_cleanup: commit 失败 err=%s",
                        e,
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass
            else:
                logger.info(
                    "[migrate] family_member_nickname_cleanup: 无空姓名脏档案，跳过清理"
                )

            # 4) 复核：仍有脏数据（含 is_self=1 的本人档）则不 ALTER
            residue_rows = (
                await db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM family_members
                        WHERE nickname IS NULL OR TRIM(nickname) = ''
                        """
                    )
                )
            ).fetchall()
            residue = int(residue_rows[0][0]) if residue_rows else 0
            if residue > 0:
                logger.error(
                    "[migrate] family_member_nickname_cleanup: 复核仍有 %d 条空姓名（可能含本人档），跳过 ALTER NOT NULL",
                    residue,
                )
                return

            # 5) ALTER 列为 NOT NULL（幂等：MySQL 同结构再 MODIFY 不会出错）
            try:
                await db.execute(
                    text(
                        "ALTER TABLE family_members MODIFY COLUMN nickname VARCHAR(100) NOT NULL"
                    )
                )
                await db.commit()
                logger.info(
                    "[migrate] family_member_nickname_cleanup: ALTER nickname NOT NULL 完成"
                )
            except Exception as e:
                logger.warning(
                    "[migrate] family_member_nickname_cleanup: ALTER 失败（可忽略，下次启动重试）err=%s",
                    e,
                )
                try:
                    await db.rollback()
                except Exception:
                    pass
    except Exception as e:
        logger.error(
            "[migrate] family_member_nickname_cleanup: 异常（不影响启动）: %s", e
        )
