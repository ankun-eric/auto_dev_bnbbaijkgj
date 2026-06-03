"""[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 B / §六]
家庭成员 ``is_self`` 一次性回填迁移：为每个 ``users`` 表中尚无 ``is_self=True``
``FamilyMember`` 记录的用户补建一条"本人"档案。

幂等：使用 ``NOT EXISTS`` 防重；可在每次启动时安全执行。
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import async_session

logger = logging.getLogger(__name__)


async def migrate_family_self() -> None:
    """补建缺失的 is_self FamilyMember 记录。"""
    try:
        async with async_session() as db:
            # 1) 先选出需要回填的用户清单（小批，避免长事务）
            # [BUG_FIX-FAMILY-NICKNAME-DEFAULT-20260530] 同步取 phone，用于兜底姓名生成
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT u.id AS uid, u.nickname AS nickname, u.phone AS phone
                        FROM users u
                        WHERE NOT EXISTS (
                            SELECT 1 FROM family_members fm
                            WHERE fm.user_id = u.id AND fm.is_self = 1
                        )
                        """
                    )
                )
            ).fetchall()

            if not rows:
                logger.info("[migrate] family_self_backfill: 0 行待回填")
                return

            inserted = 0
            for r in rows:
                uid = r[0]
                raw_nick = (r[1] or "").strip() if r[1] is not None else ""
                phone = (r[2] or "").strip() if r[2] is not None else ""
                # [BUG_FIX-FAMILY-NICKNAME-DEFAULT-20260530] 统一兜底规则：
                # 1) 先用 users.nickname；2) 否则用「用户{后4位}」；3) 兜底「用户{uid}」
                if raw_nick:
                    nickname = raw_nick
                elif phone and len(phone) >= 4:
                    nickname = f"用户{phone[-4:]}"
                else:
                    nickname = f"用户{uid}"
                try:
                    await db.execute(
                        text(
                            """
                            INSERT INTO family_members
                                (user_id, relationship_type, nickname,
                                 is_self, status, created_at)
                            VALUES
                                (:uid, 'self', :nick, 1, 'active', NOW())
                            """
                        ),
                        {"uid": uid, "nick": nickname[:100]},
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(
                        "[migrate] family_self_backfill: uid=%s insert failed err=%s",
                        uid,
                        e,
                    )

            try:
                await db.commit()
            except Exception as e:
                logger.warning(
                    "[migrate] family_self_backfill: commit failed err=%s", e
                )
                try:
                    await db.rollback()
                except Exception:
                    pass
            logger.info(
                "[migrate] family_self_backfill: 回填完成 inserted=%d / total=%d",
                inserted,
                len(rows),
            )
    except Exception as e:
        logger.error("[migrate] family_self_backfill: 异常（不影响启动）: %s", e)


async def migrate_family_self_status_to_active() -> None:
    """[BUGFIX-SELF-TAB-ALWAYS-VISIBLE-V1 2026-06-03]
    [PRD-FAMILY-V3-STATUS-INPLACE-UPGRADE 2026-06-03] V3 升级后写 'bound' 而非 'active'

    一次性把所有 ``is_self=True`` 但 status 不是 'bound' 的脏数据修正为 'bound/bound'。
    成因：早期注册流程未显式写入 status，遗留出 'pending'/'active' 等历史态记录,
    会导致顶部成员 Tab 第一格本人胶囊在按 status 过滤的接口中消失。
    幂等：可重复执行，无脏数据时为 no-op。
    """
    try:
        async with async_session() as db:
            res = await db.execute(
                text(
                    "UPDATE family_members SET status='bound', sub_status='bound' "
                    "WHERE is_self = 1 AND (status IS NULL OR status <> 'bound')"
                )
            )
            try:
                affected = res.rowcount  # MySQL 支持
            except Exception:
                affected = -1
            await db.commit()
            logger.info(
                "[migrate] family_self_status_to_active: 修正完成 affected=%s",
                affected,
            )
    except Exception as e:
        logger.error(
            "[migrate] family_self_status_to_active: 异常（不影响启动）: %s", e
        )
